"""Geometry of the 1536-d embedding cache and of the two audited questions."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
OUT = Path(sys.argv[1])
QUESTIONS = {
    "research_es": (
        "En el Miembro Galembo de la Formación La Luna, sección de Aguablanca, "
        "¿qué litofacies se consideran las más adecuadas para fracturamiento "
        "hidráulico y qué combinación de características mineralógicas y "
        "geoquímicas respalda esa interpretación? Incluye los rangos reportados "
        "de cuarzo, arcillas y TOC, y explica qué indican los valores de Tmax y "
        "del índice de producción (PI) sobre la madurez térmica de las muestras."),
    "quick_en": (
        "According to the organic matter quality and maturity section of the "
        "Galembo Member study, what are the reported Tmax and Production Index "
        "(PI) ranges for the Aguablanca samples, and how do the authors "
        "interpret them?"),
}
GALEMBO = "Casadiego-Quintero & Ríos-Reyes, 2016"
TMAX_CHUNK = "8be32c0bf964bad4"


def galembo_ids() -> list[str]:

    sql = ("SELECT c.chunk_id FROM rag.chunks c JOIN rag.documents d "
           f"USING (doc_id) WHERE d.citation = '{GALEMBO}' ORDER BY c.seq")
    out = subprocess.run(["docker", "exec", "vmm-postgis", "psql", "-U",
                          "babillard", "-d", "vmmstore", "-At", "-c", sql],
                         check=True, capture_output=True, text=True).stdout
    return out.split()


def main() -> None:

    X = np.load(ROOT / "chunks/embeddings.npy", mmap_mode="r")
    index = json.loads((ROOT / "chunks/embeddings_index.json").read_text())
    n, d = X.shape
    res: dict = {"n": n, "d": d}

    norms = np.linalg.norm(X, axis=1)
    res["norm_min_max"] = [norms.min(), norms.max()]

    mu = X.mean(axis=0)
    res["mean_norm"] = np.linalg.norm(mu)

    rng = np.random.default_rng(0)
    i, j = rng.integers(0, n, 300_000), rng.integers(0, n, 300_000)
    keep = i != j
    i, j = i[keep], j[keep]
    cos = np.concatenate([
        np.einsum("ij,ij->i", X[i[s:s + 10_000]], X[j[s:s + 10_000]])
        for s in range(0, len(i), 10_000)])
    res["pair_cos"] = {"mean": cos.mean(), "sd": cos.std(),
                       "p01": np.quantile(cos, .01),
                       "p50": np.quantile(cos, .5),
                       "p99": np.quantile(cos, .99)}
    res["isotropic_sd"] = 1 / np.sqrt(d)

    Xc = X - mu
    cov = Xc.T @ Xc / (n - 1)
    lam = np.linalg.eigvalsh(cov)[::-1]
    share = np.cumsum(lam) / lam.sum()
    res["spectrum"] = {
        "trace": lam.sum(),
        "top1_share": lam[0] / lam.sum(),
        "top10_share": share[9],
        "k50": int(np.searchsorted(share, .5) + 1),
        "k90": int(np.searchsorted(share, .9) + 1),
        "k99": int(np.searchsorted(share, .99) + 1),
        "participation_ratio": lam.sum() ** 2 / (lam ** 2).sum(),
        "lam_head": lam[:5].tolist(),
    }
    _, V = np.linalg.eigh(cov)
    V = V[:, ::-1]

    gal = galembo_ids()
    gal_rows = [index[c]["row"] for c in gal]
    G = X[gal_rows]
    gs = G @ G.T
    res["galembo"] = {
        "chunks": len(gal),
        "intra_cos_mean": gs[~np.eye(len(gal), dtype=bool)].mean(),
        "centroid_norm": np.linalg.norm(G.mean(axis=0)),
    }
    t_row = index[TMAX_CHUNK]["row"]

    from crocol.infrastructure.vectors.embeddings import embed_texts
    Q = embed_texts(list(QUESTIONS.values())).astype(np.float64)
    res["q_cos_between"] = float(Q[0] @ Q[1])

    Xn = Xc / np.linalg.norm(Xc, axis=1, keepdims=True)
    for name, q in zip(QUESTIONS, Q):
        s = X @ q
        order = np.argsort(-s)
        rank = np.empty(n, dtype=int)
        rank[order] = np.arange(1, n + 1)
        qc = q - mu
        sc = Xn @ (qc / np.linalg.norm(qc))
        rank_c = np.empty(n, dtype=int)
        rank_c[np.argsort(-sc)] = np.arange(1, n + 1)
        proj = V.T @ q
        res[name] = {
            "q_dot_mu": float(q @ mu),
            "score_mean": s.mean(), "score_sd": s.std(),
            "top10": s[order[:10]].round(4).tolist(),
            "tmax_cos": s[t_row], "tmax_rank": int(rank[t_row]),
            "tmax_z": (s[t_row] - s.mean()) / s.std(),
            "tmax_rank_centered": int(rank_c[t_row]),
            "galembo_ranks": {c: int(rank[index[c]["row"]]) for c in gal},
            "galembo_cos": {c: round(float(s[index[c]["row"]]), 4)
                            for c in gal},
            "energy_top10_pcs": float((proj[:10] ** 2).sum()),
            "energy_top100_pcs": float((proj[:100] ** 2).sum()),
            "energy_on_mu_dir": float((q @ mu / np.linalg.norm(mu)) ** 2),
        }

    k = 10
    counts = np.zeros(n, dtype=int)
    for start in range(0, n, 1000):
        block = X[start:start + 1000] @ X.T
        rows = np.arange(block.shape[0])
        block[rows, start + rows] = -np.inf
        nn = np.argpartition(-block, k, axis=1)[:, :k]
        np.add.at(counts, nn.ravel(), 1)
    m, sd = counts.mean(), counts.std()
    res["hubness"] = {"k": k, "skew": float(((counts - m) ** 3).mean() / sd ** 3),
                      "max_Nk": int(counts.max()),
                      "zero_Nk": int((counts == 0).sum()),
                      "tmax_Nk": int(counts[t_row])}

    OUT.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
