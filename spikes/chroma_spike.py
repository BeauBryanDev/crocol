"""Phase 0 spike: verify Chroma Cloud hybrid search for the VMM plan (VMM_PLAN.md section 0).

C1  Rrf with three rankings (dense + bm25 + sparse)
C2  two sparse indexes (bm25 + SPLADE) in one collection
C3  Spanish lexical behaviour: raw vs normalized BM25, SPLADE on Spanish
C4  metadata types/size limits and get-by-ids latency

Uses a temporary collection <COLLECTION_NAME>_spike, deleted at the end unless --keep.

Usage:
    magdalena/bin/python spikes/chroma_spike.py [--sample 200] [--keep]
"""

import argparse
import json
import os
import random
import re
import statistics
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
from crocol.domains.services.lexical import STOPWORDS, normalize_lexical  # noqa: E402

DENSE_MODEL = "text-embedding-3-large"
DENSE_DIMS = 1536
CHUNK_CHARS = 2800
SEED = 7
TOP_K = 5
FRONT_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
PAGE_RE = re.compile(r"<!-- page (\d+)(?::[^>]*)? -->")
TABLE_RE = re.compile(r"<!-- table ([^|]+?) \|")

PROBES = [
    ("artículo 2.1.1.1 objeto del decreto 1073 de 2015", "Decreto-1073", "compilar"),
    ("¿Qué es el abandono de pozos según la ANH?", "glosario_anh", "taponamiento"),
    ("reservas probadas de gas natural a 31 de diciembre de 2025", "Hist", "GAS NATURAL"),
    ("coordenadas norte este del área contratada VMM 53 anexo B", "CONTRATO_EP_VMM_53", "NORTE"),
    ("análisis electrofacial pozo Cagüi-1 sweet spots", "Santiago_DiazHoyos", "Cag"),
    ("sweet spot areas for shale oil in Upper Cretaceous rocks of the Middle Magdalena Valley",
     "feart-11-1146126", "sweet spot"),
    ("litofacies del miembro Galembo de la Formación La Luna", "galembo", "Galembo"),
    ("velocidades acústicas de rocas del Valle Medio del Magdalena", "Martinez_Alarcon", "acústic"),
    ("cambio de la modalidad de pago de las regalías de crudo", "Cambio_de_Modalidad", "modalidad"),
    ("valor económico de exclusividad garantía contrato E&P", "CONTRATO_", "Exclusividad"),
]


def front_matter(text):
    match = FRONT_RE.match(text)
    meta = {}
    if match:
        for line in match.group(1).splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                meta[key.strip()] = value.strip().strip('"')
    return meta, text[match.end():] if match else text


def crude_chunks(md_path):
    meta, body = front_matter(md_path.read_text(encoding="utf-8"))
    page, heading, buffer, chunks = 1, "", [], []

    def flush(kind="text", table_id=""):
        text = "\n\n".join(buffer).strip()
        if len(text) > 200:
            chunks.append({"text": text, "page": page, "heading": heading, "chunk_type": kind,
                           "table_id": table_id, **meta})
        buffer.clear()

    for block in re.split(r"\n{2,}", body):
        page_match = PAGE_RE.search(block)
        if page_match:
            page = int(page_match.group(1))
            continue
        table_match = TABLE_RE.match(block)
        if table_match:
            flush()
            buffer.append(block)
            continue
        if block.startswith("|") and buffer and buffer[0].startswith("<!-- table"):
            buffer.append(block)
            flush("table", TABLE_RE.match(buffer[0]).group(1) if buffer else "")
            continue
        if block.startswith("#"):
            flush()
            heading = block.lstrip("#").strip()[:200]
        buffer.append(block)
        if sum(len(b) for b in buffer) >= CHUNK_CHARS:
            flush()
    flush()
    return chunks


def select_sample(all_chunks, size, rng):
    chosen = {}
    for _, doc_hint, needle in PROBES:
        hits = [c for c in all_chunks if doc_hint.lower() in c["source_path"].lower()
                and needle.lower() in c["text"].lower()]
        for chunk in hits[:3]:
            chosen[id(chunk)] = chunk
    rest = [c for c in all_chunks if id(c) not in chosen]
    rng.shuffle(rest)
    by_collection = {}
    for chunk in rest:
        by_collection.setdefault(chunk.get("collection", "?"), []).append(chunk)
    while len(chosen) < size and any(by_collection.values()):
        for items in by_collection.values():
            if items and len(chosen) < size:
                chunk = items.pop()
                chosen[id(chunk)] = chunk
    return list(chosen.values())


def embed(client, texts):
    vectors = []
    for start in range(0, len(texts), 64):
        batch = [t[:24000] for t in texts[start:start + 64]]
        for attempt in range(5):
            try:
                response = client.embeddings.create(model=DENSE_MODEL, input=batch, dimensions=DENSE_DIMS)
                vectors.extend(item.embedding for item in response.data)
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(2 ** attempt)
    return vectors


def timed(fn):
    start = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - start) * 1000


def record(results, name, ok, detail):
    results[name] = {"ok": ok, "detail": detail}
    print(f"  {'OK  ' if ok else 'FAIL'} {name}: {detail}")


def search_ids(collection, rank, n=TOP_K, where=None):
    search = Search().rank(rank).limit(n).select(K.DOCUMENT)
    if where is not None:
        search = search.where(where)
    rows = collection.search(search).rows()[0]
    return [row["id"] for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=200)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--markdown", type=Path, default=ROOT / "markdown")
    parser.add_argument("--report", type=Path, default=ROOT / "spikes" / "chroma_spike_report.json")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    rng = random.Random(SEED)
    results, timings = {}, {}

    print("Sample")
    all_chunks = []
    for md in sorted(args.markdown.glob("*.md")):
        all_chunks.extend(crude_chunks(md))
    sample = select_sample(all_chunks, args.sample, rng)
    for index, chunk in enumerate(sample):
        chunk["id"] = f"spike-{index:04d}"
        chunk["lexical_text"] = normalize_lexical(chunk["text"])
    print(f"  {len(all_chunks)} crude chunks from {len(list(args.markdown.glob('*.md')))} docs; "
          f"sampled {len(sample)}")

    print("Dense embeddings")
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    vectors, ms = timed(lambda: embed(openai_client, [c["text"] for c in sample]))
    timings["embed_docs_ms"] = round(ms)
    print(f"  {len(vectors)} x {len(vectors[0])} in {ms / 1000:.1f}s")

    chroma = chromadb.CloudClient(tenant=os.environ["CHROMA_TENANT"],
                                  database=os.environ["CHROMA_DATABASE"],
                                  api_key=os.environ["CHROMA_API_KEY"])
    collection_name = f"{os.environ['COLLECTION_NAME']}_spike"
    try:
        chroma.delete_collection(collection_name)
    except Exception:
        pass

    print("C2 schema with two sparse indexes")
    bm25_ef = ChromaBm25EmbeddingFunction(stopwords=STOPWORDS)
    two_sparse = True
    try:
        schema = (Schema()
                  .create_index(config=VectorIndexConfig(space="cosine", embedding_function=None))
                  .create_index(config=SparseVectorIndexConfig(embedding_function=bm25_ef,
                                                               source_key="lexical_text", bm25=True),
                                key="bm25")
                  .create_index(config=SparseVectorIndexConfig(
                      embedding_function=ChromaCloudSpladeEmbeddingFunction(),
                      source_key=K.DOCUMENT), key="sparse"))
        collection = chroma.create_collection(name=collection_name, schema=schema,
                                              metadata={"dense_model": DENSE_MODEL,
                                                        "dense_dims": DENSE_DIMS})
        record(results, "C2_two_sparse_indexes", True, "bm25 (source lexical_text) + sparse (SPLADE)")
    except Exception as exc:
        two_sparse = False
        record(results, "C2_two_sparse_indexes", False, f"{type(exc).__name__}: {str(exc)[:200]}")
        schema = (Schema()
                  .create_index(config=VectorIndexConfig(space="cosine", embedding_function=None))
                  .create_index(config=SparseVectorIndexConfig(embedding_function=bm25_ef,
                                                               source_key="lexical_text", bm25=True),
                                key="bm25"))
        collection = chroma.create_collection(name=collection_name, schema=schema)

    print("C4 add with metadata types")
    metadatas = []
    for chunk in sample:
        metadatas.append({
            "source_path": chunk.get("source_path", ""), "collection": chunk.get("collection", ""),
            "doc_type": chunk.get("doc_type", ""), "chunk_type": chunk["chunk_type"],
            "heading_path": chunk["heading"], "page_start": int(chunk["page"]),
            "ocr_source": chunk.get("producer", "").startswith(("PFU", "Kodak")),
            "year_f": float(chunk.get("year") or 0), "lexical_text": chunk["lexical_text"],
        })
    try:
        _, ms = timed(lambda: [collection.add(ids=[c["id"] for c in sample[i:i + 50]],
                                              documents=[c["text"] for c in sample[i:i + 50]],
                                              embeddings=vectors[i:i + 50],
                                              metadatas=metadatas[i:i + 50])
                               for i in range(0, len(sample), 50)])
        timings["add_ms"] = round(ms)
        record(results, "C4_metadata_types", True,
               f"str/int/bool/float + lexical_text up to {max(len(m['lexical_text']) for m in metadatas)} chars; "
               f"count={collection.count()}")
    except Exception as exc:
        record(results, "C4_metadata_types", False, f"{type(exc).__name__}: {str(exc)[:300]}")
        print("cannot continue without data")
        return finish(chroma, collection_name, args, results, timings)

    ids = [c["id"] for c in sample[:50]]
    lat = []
    for _ in range(3):
        _, ms = timed(lambda: collection.get(ids=ids, include=["documents", "metadatas"]))
        lat.append(ms)
    timings["get_50_ids_ms_median"] = round(statistics.median(lat))
    record(results, "C4_get_by_ids", True, f"50 ids, median {timings['get_50_ids_ms_median']} ms")

    print("C1 three-way Rrf")
    probe_vec = embed(openai_client, [PROBES[0][0]])[0]
    q_lex = normalize_lexical(PROBES[0][0])
    q_bm25 = bm25_ef.embed_query([q_lex])[0]
    channels = {
        "dense": lambda v, raw, bm: Knn(query=v, return_rank=True, limit=100),
        "bm25": lambda v, raw, bm: Knn(query=bm, key="bm25", return_rank=True, limit=100),
    }
    if two_sparse:
        channels["sparse"] = lambda v, raw, bm: Knn(query=raw, key="sparse", return_rank=True, limit=100)
    try:
        rank = Rrf(ranks=[make(probe_vec, PROBES[0][0], q_bm25) for make in channels.values()],
                   weights=[1.0, 1.0, 0.5][:len(channels)], k=60)
        hits, ms = timed(lambda: search_ids(collection, rank))
        timings["rrf3_search_ms"] = round(ms)
        record(results, "C1_rrf_three_rankings", len(channels) == 3,
               f"{len(channels)} rankings fused server-side, {round(ms)} ms, top={hits[:3]}")
    except Exception as exc:
        record(results, "C1_rrf_three_rankings", False, f"{type(exc).__name__}: {str(exc)[:200]}")

    print("C3 retrieval probes (hit@5)")
    known = rng.sample(sample, 20)
    probe_set = [(q, h, n) for q, h, n in PROBES]
    for chunk in known:
        sentences = [s for s in re.split(r"(?<=[.;:])\s+", chunk["text"]) if 60 <= len(s) <= 220]
        if sentences:
            probe_set.append((rng.choice(sentences), chunk["id"], None))
    vecs = embed(openai_client, [q for q, _, _ in probe_set])
    scores = {name: [] for name in ["dense", "bm25_raw", "bm25_norm", "sparse", "rrf_dense_bm25", "rrf3"]}
    for (query, target, needle), vec in zip(probe_set, vecs):
        def relevant(cid):
            chunk = sample[int(cid.split("-")[1])]
            if needle is None:
                return cid == target
            return target.lower() in chunk["source_path"].lower() and needle.lower() in chunk["text"].lower()
        bm_norm = bm25_ef.embed_query([normalize_lexical(query)])[0]
        bm_raw = bm25_ef.embed_query([query])[0]
        runs = {
            "dense": Knn(query=vec, limit=TOP_K),
            "bm25_raw": Knn(query=bm_raw, key="bm25", limit=TOP_K),
            "bm25_norm": Knn(query=bm_norm, key="bm25", limit=TOP_K),
            "rrf_dense_bm25": Rrf(ranks=[Knn(query=vec, return_rank=True, limit=100),
                                         Knn(query=bm_norm, key="bm25", return_rank=True, limit=100)],
                                  k=60),
        }
        if two_sparse:
            runs["sparse"] = Knn(query=query, key="sparse", limit=TOP_K)
            runs["rrf3"] = Rrf(ranks=[Knn(query=vec, return_rank=True, limit=100),
                                      Knn(query=bm_norm, key="bm25", return_rank=True, limit=100),
                                      Knn(query=query, key="sparse", return_rank=True, limit=100)],
                               weights=[1.0, 1.0, 0.5], k=60)
        for name, rank in runs.items():
            try:
                hits = search_ids(collection, rank)
                scores[name].append(next((1 / (i + 1) for i, h in enumerate(hits) if relevant(h)), 0.0))
            except Exception as exc:
                scores[name].append(None)
                results.setdefault(f"error_{name}", {"ok": False, "detail": str(exc)[:200]})
    summary = {}
    for name, values in scores.items():
        valid = [v for v in values if v is not None]
        if valid:
            summary[name] = {"hit@5": round(sum(1 for v in valid if v > 0) / len(valid), 3),
                             "mrr@5": round(sum(valid) / len(valid), 3), "n": len(valid)}
            print(f"  {name:16} hit@5={summary[name]['hit@5']:.2f}  mrr@5={summary[name]['mrr@5']:.2f}  "
                  f"(n={len(valid)})")
    results["C3_probe_scores"] = {"ok": True, "detail": summary}
    gain = summary.get("bm25_norm", {}).get("hit@5", 0) - summary.get("bm25_raw", {}).get("hit@5", 0)
    record(results, "C3_normalized_bm25_gain", gain >= 0, f"hit@5 gain normalized vs raw: {gain:+.2f}")
    return finish(chroma, collection_name, args, results, timings)


def finish(chroma, name, args, results, timings):
    if not args.keep:
        try:
            chroma.delete_collection(name)
            print(f"deleted temporary collection {name}")
        except Exception as exc:
            print(f"could not delete {name}: {exc}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"results": results, "timings_ms": timings,
                                       "dense_model": DENSE_MODEL, "dense_dims": DENSE_DIMS},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
