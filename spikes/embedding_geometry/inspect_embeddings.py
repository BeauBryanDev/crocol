"""Inspect the cached embeddings of a trace's top-k chunks.

Usage (repo root):
    magdalena/bin/python <this file> <trace_id> [--query "question text"]

--query embeds the text once with OpenAI (fractions of a cent) and ranks the
top-k by cosine, so dense similarity can be compared with the stored scores.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path.cwd()
SQL = """
SELECT qc.rank, qc.chunk_id, coalesce(qc.score, 'NaN'),
       coalesce(d.citation, '-'), coalesce(c.chunk_type, '-')
FROM ops.query_chunks qc
LEFT JOIN rag.chunks c USING (chunk_id)
LEFT JOIN rag.documents d USING (doc_id)
WHERE qc.trace_id = '{tid}' AND qc.stage = 'retrieved'
ORDER BY qc.rank
"""


def top_k(trace_id: str) -> list[tuple]:

    out = subprocess.run(
        ["docker", "exec", "vmm-postgis", "psql", "-U", "babillard",
         "-d", "vmmstore", "-At", "-F", "\t",
         "-c", SQL.format(tid=trace_id)],
        check=True, capture_output=True, text=True).stdout
    rows = [line.split("\t") for line in out.splitlines() if line]
    return [(int(r), cid, float(s), cit, ctype)
            for r, cid, s, cit, ctype in rows]


def main() -> None:

    parser = argparse.ArgumentParser()
    parser.add_argument("trace_id")
    parser.add_argument("--query")
    args = parser.parse_args()

    vectors = np.load(ROOT / "chunks/embeddings.npy", mmap_mode="r")
    index = json.loads((ROOT / "chunks/embeddings_index.json").read_text())
    rows = [r for r in top_k(args.trace_id) if r[1] in index]
    matrix = np.stack([vectors[index[r[1]]["row"]] for r in rows])

    print(f"cache: {vectors.shape[0]} vectors x {vectors.shape[1]} dims")
    query = None
    if args.query:
        from crocol.infrastructure.vectors.embeddings import embed_query
        query = np.asarray(embed_query(args.query), dtype=np.float32)

    print(f"{'rk':>2} {'chunk_id':16} {'score':>7} {'cos_q':>6} "
          f"{'norm':>5}  first 5 dims / citation")
    for (rank, cid, score, cit, ctype), vec in zip(rows, matrix):
        cos = f"{float(vec @ query):6.3f}" if query is not None else "     -"
        head = " ".join(f"{x:+.3f}" for x in vec[:5])
        print(f"{rank:2d} {cid} {score:7.4f} {cos} "
              f"{np.linalg.norm(vec):5.3f}  [{head}] {ctype} {cit}")

    sims = matrix @ matrix.T
    np.fill_diagonal(sims, np.nan)
    print(f"\npairwise cosine among top-k: mean {np.nanmean(sims):.3f}, "
          f"max {np.nanmax(sims):.3f}")
    pairs = np.argwhere(sims > 0.9)
    for i, j in pairs[pairs[:, 0] < pairs[:, 1]]:
        print(f"  near-duplicate: {rows[i][1]} ~ {rows[j][1]} "
              f"({sims[i, j]:.3f})")


if __name__ == "__main__":
    main()
