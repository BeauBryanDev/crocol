"""Phase 0 follow-up: does Chroma-hosted SPLADE add value when it must live in its own collection?

Chroma allows one sparse index per collection (C2 failed), so SPLADE would need a second
collection and client-side fusion. This compares, on the same sample and probes as
chroma_spike.py:
  dense, bm25 (normalized), splade, rrf(dense+bm25) server-side, rrf(dense+bm25+splade) client-side

Usage:
    magdalena/bin/python spikes/splade_check.py [--sample 200]
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import chromadb
from chromadb import K, Knn, Rrf, Schema, Search, SparseVectorIndexConfig, VectorIndexConfig
from chromadb.utils.embedding_functions import (ChromaBm25EmbeddingFunction,
                                                ChromaCloudSpladeEmbeddingFunction)
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "spikes"))
from chroma_spike import PROBES, SEED, crude_chunks, embed, select_sample  # noqa: E402
from crocol.domains.services.lexical import STOPWORDS, normalize_lexical  # noqa: E402

TOP_K = 5
CANDIDATES = 100
RRF_K = 60


def ranked_ids(collection, rank, n):
    rows = collection.search(Search().rank(rank).limit(n).select(K.SCORE)).rows()[0]
    return [row["id"] for row in rows]


def rrf(lists, weights):
    scores = {}
    for ids, weight in zip(lists, weights):
        for position, cid in enumerate(ids):
            scores[cid] = scores.get(cid, 0.0) + weight / (RRF_K + position + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda item: -item[1])]


def build(chroma, name, schema, sample, vectors, with_lexical):
    try:
        chroma.delete_collection(name)
    except Exception:
        pass
    collection = chroma.create_collection(name=name, schema=schema)
    for start in range(0, len(sample), 50):
        part = sample[start:start + 50]
        collection.add(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            embeddings=vectors[start:start + 50],
            metadatas=[{"source_path": c.get("source_path", ""),
                        **({"lexical_text": c["lexical_text"]} if with_lexical else {})} for c in part],
        )
    return collection


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--report", type=Path, default=ROOT / "spikes" / "splade_check_report.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    rng = random.Random(SEED)

    all_chunks = []
    for md in sorted((ROOT / "markdown").glob("*.md")):
        all_chunks.extend(crude_chunks(md))
    sample = select_sample(all_chunks, args.sample, rng)
    for index, chunk in enumerate(sample):
        chunk["id"] = f"spike-{index:04d}"
        chunk["lexical_text"] = normalize_lexical(chunk["text"])

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    vectors = embed(openai_client, [c["text"] for c in sample])
    chroma = chromadb.CloudClient(tenant=os.environ["CHROMA_TENANT"],
                                  database=os.environ["CHROMA_DATABASE"],
                                  api_key=os.environ["CHROMA_API_KEY"])
    base = os.environ["COLLECTION_NAME"]
    bm25_ef = ChromaBm25EmbeddingFunction(stopwords=STOPWORDS)
    main_schema = (Schema()
                   .create_index(config=VectorIndexConfig(space="cosine", embedding_function=None))
                   .create_index(config=SparseVectorIndexConfig(embedding_function=bm25_ef,
                                                                source_key="lexical_text", bm25=True),
                                 key="bm25"))
    splade_schema = (Schema()
                     .create_index(config=VectorIndexConfig(space="cosine", embedding_function=None))
                     .create_index(config=SparseVectorIndexConfig(
                         embedding_function=ChromaCloudSpladeEmbeddingFunction(),
                         source_key=K.DOCUMENT), key="splade"))
    names = [f"{base}_spike", f"{base}_spike_splade"]
    try:
        start = time.perf_counter()
        main_col = build(chroma, names[0], main_schema, sample, vectors, True)
        splade_col = build(chroma, names[1], splade_schema, sample, vectors, False)
        print(f"collections built in {time.perf_counter() - start:.1f}s")

        probe_set = list(PROBES)
        for chunk in random.Random(SEED + 1).sample(sample, 25):
            sentences = [s for s in re.split(r"(?<=[.;:])\s+", chunk["text"]) if 60 <= len(s) <= 220]
            if sentences:
                probe_set.append((random.Random(chunk["id"]).choice(sentences), chunk["id"], None))
        query_vecs = embed(openai_client, [q for q, _, _ in probe_set])

        names_runs = ["dense", "bm25", "splade", "rrf_dense_bm25", "rrf_dense_bm25_splade"]
        scores = {n: [] for n in names_runs}
        latency = {n: [] for n in ["dense_bm25_server", "splade"]}
        for (query, target, needle), vec in zip(probe_set, query_vecs):
            def relevant(cid):
                chunk = sample[int(cid.split("-")[1])]
                if needle is None:
                    return cid == target
                return (target.lower() in chunk["source_path"].lower()
                        and needle.lower() in chunk["text"].lower())
            bm = bm25_ef.embed_query([normalize_lexical(query)])[0]
            dense_ids = ranked_ids(main_col, Knn(query=vec, limit=CANDIDATES), CANDIDATES)
            bm25_ids = ranked_ids(main_col, Knn(query=bm, key="bm25", limit=CANDIDATES), CANDIDATES)
            t0 = time.perf_counter()
            splade_ids = ranked_ids(splade_col, Knn(query=query, key="splade", limit=CANDIDATES), CANDIDATES)
            latency["splade"].append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            server = ranked_ids(main_col, Rrf(ranks=[Knn(query=vec, return_rank=True, limit=CANDIDATES),
                                                     Knn(query=bm, key="bm25", return_rank=True,
                                                         limit=CANDIDATES)], k=RRF_K), TOP_K)
            latency["dense_bm25_server"].append((time.perf_counter() - t0) * 1000)
            runs = {
                "dense": dense_ids, "bm25": bm25_ids, "splade": splade_ids, "rrf_dense_bm25": server,
                "rrf_dense_bm25_splade": rrf([dense_ids, bm25_ids, splade_ids], [1.0, 1.0, 0.5]),
            }
            for name, ids in runs.items():
                top = ids[:TOP_K]
                scores[name].append(next((1 / (i + 1) for i, h in enumerate(top) if relevant(h)), 0.0))

        summary = {name: {"hit@5": round(sum(1 for v in vals if v > 0) / len(vals), 3),
                          "mrr@5": round(sum(vals) / len(vals), 3), "n": len(vals)}
                   for name, vals in scores.items()}
        for name, s in summary.items():
            print(f"  {name:22} hit@5={s['hit@5']:.2f}  mrr@5={s['mrr@5']:.2f}  (n={s['n']})")
        lat = {k: round(sorted(v)[len(v) // 2]) for k, v in latency.items()}
        print(f"  median latency ms: {lat}")
        split = {"curated_probes": {}, "known_item": {}}
        for name, vals in scores.items():
            split["curated_probes"][name] = round(sum(1 for v in vals[:len(PROBES)] if v > 0) / len(PROBES), 2)
            rest = vals[len(PROBES):]
            split["known_item"][name] = round(sum(1 for v in rest if v > 0) / max(1, len(rest)), 2)
        print(f"  hit@5 curated probes (n={len(PROBES)}): {split['curated_probes']}")
        print(f"  hit@5 known-item sentences (n={len(probe_set) - len(PROBES)}): {split['known_item']}")
        args.report.write_text(json.dumps({"summary": summary, "split_hit@5": split,
                                           "median_latency_ms": lat}, indent=2), encoding="utf-8")
        print(f"report: {args.report}")
    finally:
        for name in names:
            try:
                chroma.delete_collection(name)
            except Exception:
                pass
        print("temporary collections deleted")


if __name__ == "__main__":
    main()
