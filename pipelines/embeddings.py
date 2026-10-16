"""Dense embeddings with OpenAI text-embedding-3-large (1536-d), cached by content hash.

The cache (chunks/embeddings.npy + chunks/embeddings_index.json) maps chunk_id to the sha1 of
the embedded text, so re-runs only embed chunks whose text changed.

Usage:
    magdalena/bin/python pipelines/embeddings.py [--chunks chunks/chunks.jsonl]
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

from config.settings import EMBED_BATCH, EMBED_DIMS, EMBED_MODEL, ROOT
from crocol.infrastructure.vectors.embeddings import client, embed_texts

CACHE_VECTORS = ROOT / "chunks" / "embeddings.npy"
CACHE_INDEX = ROOT / "chunks" / "embeddings_index.json"


def content_hash(text):
    return hashlib.sha1(f"{EMBED_MODEL}|{EMBED_DIMS}|{text}".encode("utf-8")).hexdigest()


def load_cache():
    if not (CACHE_VECTORS.exists() and CACHE_INDEX.exists()):
        return {}, np.zeros((0, EMBED_DIMS), dtype=np.float32)
    index = json.loads(CACHE_INDEX.read_text(encoding="utf-8"))
    return index, np.load(CACHE_VECTORS)


def embed_chunks(records):
    index, matrix = load_cache()
    vectors, todo = {}, []
    for record in records:
        digest = content_hash(record["embed_text"])
        cached = index.get(record["chunk_id"])
        if cached and cached["hash"] == digest:
            vectors[record["chunk_id"]] = matrix[cached["row"]]
        else:
            todo.append((record["chunk_id"], digest, record["embed_text"]))
    print(f"chunks {len(records)}: cached {len(vectors)}, to embed {len(todo)}", file=sys.stderr)
    if todo:
        oc = client()
        started = time.perf_counter()
        for start in range(0, len(todo), EMBED_BATCH * 8):
            part = todo[start:start + EMBED_BATCH * 8]
            fresh = embed_texts([t for _, _, t in part], oc)
            for (chunk_id, _, _), vector in zip(part, fresh):
                vectors[chunk_id] = vector
            done = min(start + len(part), len(todo))
            print(f"  embedded {done}/{len(todo)} ({time.perf_counter() - started:.0f}s)", file=sys.stderr)
    ordered = [r["chunk_id"] for r in records]
    new_matrix = np.stack([vectors[cid] for cid in ordered]).astype(np.float32)
    new_index = {cid: {"row": i, "hash": content_hash(r["embed_text"])} for i, (cid, r) in
                 enumerate(zip(ordered, records))}
    CACHE_VECTORS.parent.mkdir(parents=True, exist_ok=True)
    np.save(CACHE_VECTORS, new_matrix)
    CACHE_INDEX.write_text(json.dumps(new_index), encoding="utf-8")
    return new_matrix, len(todo)


def read_chunks(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chunks", type=Path, default=ROOT / "chunks" / "chunks.jsonl")
    args = parser.parse_args()
    records = read_chunks(args.chunks)
    matrix, fresh = embed_chunks(records)
    print(f"vectors {matrix.shape}, newly embedded {fresh}")


if __name__ == "__main__":
    main()
