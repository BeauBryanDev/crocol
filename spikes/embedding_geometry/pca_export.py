"""PCA of the embedding cache to 3 components; run with the magdalena venv.

Reads chunks/embeddings.npy memory-mapped and in blocks (peak ~150 MB) and
writes a small .npz for pca_plot.py, which runs where matplotlib lives.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
BLOCK = 2000
QUESTIONS = {
    "Research Q (ES)": (
        "En el Miembro Galembo de la Formación La Luna, sección de Aguablanca, "
        "¿qué litofacies se consideran las más adecuadas para fracturamiento "
        "hidráulico y qué combinación de características mineralógicas y "
        "geoquímicas respalda esa interpretación? Incluye los rangos reportados "
        "de cuarzo, arcillas y TOC, y explica qué indican los valores de Tmax y "
        "del índice de producción (PI) sobre la madurez térmica de las muestras."),
    "Quick Q (EN)": (
        "According to the organic matter quality and maturity section of the "
        "Galembo Member study, what are the reported Tmax and Production Index "
        "(PI) ranges for the Aguablanca samples, and how do the authors "
        "interpret them?"),
}
QUICK_TRACE = "d82994ac-ffa9-454f-9929-23ce5ff1a02b"
SQL_META = """
SELECT c.chunk_id, d.collection, d.citation
FROM rag.chunks c JOIN rag.documents d USING (doc_id)
"""
SQL_GALEMBO = """
SELECT c.chunk_id, c.seq FROM rag.chunks c JOIN rag.documents d USING (doc_id)
WHERE d.citation = 'Casadiego-Quintero & Ríos-Reyes, 2016' ORDER BY c.seq
"""
SQL_TOPK = f"""
SELECT chunk_id FROM ops.query_chunks
WHERE trace_id = '{QUICK_TRACE}' AND stage = 'retrieved'
"""


def psql(sql: str) -> list[list[str]]:

    out = subprocess.run(["docker", "exec", "vmm-postgis", "psql", "-U",
                          "babillard", "-d", "vmmstore", "-At", "-F", "\t",
                          "-c", sql],
                         check=True, capture_output=True, text=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def main() -> None:

    X = np.load(ROOT / "chunks/embeddings.npy", mmap_mode="r")
    index = json.loads((ROOT / "chunks/embeddings_index.json").read_text())
    n, d = X.shape

    mu = np.zeros(d)
    for s in range(0, n, BLOCK):
        mu += X[s:s + BLOCK].sum(axis=0, dtype=np.float64)
    mu /= n

    cov = np.zeros((d, d))
    for s in range(0, n, BLOCK):
        block = X[s:s + BLOCK].astype(np.float64) - mu
        cov += block.T @ block
    cov /= n - 1

    lam, V = np.linalg.eigh(cov)
    lam, V = lam[::-1], V[:, ::-1][:, :3]
    explained = lam[:3] / lam.sum()

    coords = np.empty((n, 3), dtype=np.float32)
    for s in range(0, n, BLOCK):
        coords[s:s + BLOCK] = (X[s:s + BLOCK].astype(np.float64) - mu) @ V

    from crocol.infrastructure.vectors.embeddings import embed_texts
    Q = embed_texts(list(QUESTIONS.values())).astype(np.float64)
    q_coords = (Q - mu) @ V

    ids = np.empty(n, dtype=object)
    for cid, entry in index.items():
        ids[entry["row"]] = cid
    meta = {cid: (col, cit) for cid, col, cit in psql(SQL_META)}
    topk = {row[0] for row in psql(SQL_TOPK)}

    galembo = psql(SQL_GALEMBO)
    G = np.stack([X[index[cid]["row"]] for cid, _ in galembo]).astype(np.float64)
    g_mu = G.mean(axis=0)
    _, sv, Vt = np.linalg.svd(G - g_mu, full_matrices=False)
    g_basis = Vt[:3].T
    g_explained = sv[:3] ** 2 / (sv ** 2).sum()

    np.savez_compressed(
        sys.argv[1],
        g_coords=((G - g_mu) @ g_basis).astype(np.float32),
        g_q_coords=((Q - g_mu) @ g_basis).astype(np.float32),
        g_explained=g_explained,
        g_ids=np.array([cid for cid, _ in galembo]),
        g_seq=np.array([int(seq) for _, seq in galembo]),
        g_q_cos=(Q @ G.T).astype(np.float32),
        coords=coords,
        explained=explained,
        q_coords=q_coords.astype(np.float32),
        q_names=np.array(list(QUESTIONS)),
        collection=np.array([meta.get(c, ("?", "?"))[0] for c in ids]),
        citation=np.array([meta.get(c, ("?", "?"))[1] for c in ids]),
        chunk_id=ids.astype(str),
        in_topk=np.array([c in topk for c in ids]),
    )
    print(f"saved {n} points; explained variance PC1-3: "
          f"{np.round(explained * 100, 2)} % (sum {explained.sum():.1%})")


if __name__ == "__main__":
    main()
