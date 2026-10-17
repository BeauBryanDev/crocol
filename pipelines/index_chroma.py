"""Create (if needed) and sync the Chroma Cloud collection with chunks/chunks.jsonl.

Schema (Phase 0 decision): precomputed dense vectors (1536-d, cosine) + one BM25 sparse
index on the metadata field lexical_text. Upserts every chunk, deletes ids no longer present.

Usage:
    magdalena/bin/python pipelines/index_chroma.py [--chunks chunks/chunks.jsonl] [--batch 100]
"""

import argparse
import sys
import time
from pathlib import Path

from chromadb import Schema, SparseVectorIndexConfig, VectorIndexConfig
from chromadb.utils.embedding_functions import ChromaBm25EmbeddingFunction

from chunking import PIPELINE_VERSION
from config.settings import BM25_KEY, BM25_SOURCE_KEY, EMBED_DIMS, EMBED_MODEL, ROOT, get_settings
from crocol.domains.services.lexical import STOPWORDS
from crocol.infrastructure.vectors.chroma_store import chroma_client
from embeddings import embed_chunks, read_chunks

METADATA_FIELDS = [
    "doc_id", "source_path", "collection", "doc_type", "language", "title", "authors", "year",
    "institution", "citation", "venue", "doi", "topics", "formations",
    "ocr_source", "area", "basin", "contractor", "regulation", "document_status", "chunk_type",
    "heading_path", "page_start", "page_end", "table_id", "article", "clause", "lexical_text",
]
MAX_METADATA_KEYS = 32


def collection_schema():
    return (Schema()
            .create_index(config=VectorIndexConfig(space="cosine", embedding_function=None))
            .create_index(config=SparseVectorIndexConfig(
                embedding_function=ChromaBm25EmbeddingFunction(stopwords=STOPWORDS),
                source_key=BM25_SOURCE_KEY, bm25=True), key=BM25_KEY))


def get_or_create(client, name):
    existing = {c.name for c in client.list_collections()}
    if name in existing:
        collection = client.get_collection(name)
        meta = collection.metadata or {}
        if meta.get("dense_model") != EMBED_MODEL or int(meta.get("dense_dims", 0)) != EMBED_DIMS:
            sys.exit(f"collection {name} exists with dense_model={meta.get('dense_model')} "
                     f"dims={meta.get('dense_dims')}; expected {EMBED_MODEL}/{EMBED_DIMS}. Not touching it.")
        print(f"using existing collection {name}")
        return collection
    print(f"creating collection {name}")
    return client.create_collection(name=name, schema=collection_schema(),
                                    metadata={"dense_model": EMBED_MODEL, "dense_dims": EMBED_DIMS,
                                              "pipeline_version": PIPELINE_VERSION,
                                              "space": "cosine", "sparse": f"{BM25_KEY}:{BM25_SOURCE_KEY}"})


def metadata_of(record):
    out = {}
    for key in METADATA_FIELDS:
        value = record.get(key)
        if value is None:
            value = ""
        if isinstance(value, (list, dict)):
            value = str(value)
        out[key] = value
    return out


def existing_ids(collection, page=300):
    ids, offset = set(), 0
    while True:
        result = collection.get(include=[], limit=page, offset=offset)
        batch = result.get("ids") or []
        ids.update(batch)
        if len(batch) < page:
            return ids
        offset += page


def retry(fn, attempts=6):
    for attempt in range(attempts):
        try:
            return fn()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(min(30, 2 ** attempt))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chunks", type=Path, default=ROOT / "chunks" / "chunks.jsonl")
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--new-only", action="store_true",
                        help="upsert only chunk ids not yet in Chroma (unchanged chunks keep their ids)")
    args = parser.parse_args()

    if len(METADATA_FIELDS) + 1 > MAX_METADATA_KEYS:
        sys.exit(f"{len(METADATA_FIELDS)} metadata fields + sparse key exceed Chroma's {MAX_METADATA_KEYS}")
    records = read_chunks(args.chunks)
    ids = [r["chunk_id"] for r in records]
    if len(set(ids)) != len(ids):
        sys.exit("duplicate chunk_id values in chunks.jsonl")
    matrix, fresh = embed_chunks(records)

    client = chroma_client()
    collection = get_or_create(client, get_settings().collection_name)
    before = existing_ids(collection)
    stale = sorted(before - set(ids))

    positions = [i for i, r in enumerate(records) if not args.new_only or r["chunk_id"] not in before]
    started = time.perf_counter()
    for start in range(0, len(positions), args.batch):
        part = positions[start:start + args.batch]
        retry(lambda: collection.upsert(
            ids=[records[i]["chunk_id"] for i in part],
            documents=[records[i]["text"] for i in part],
            embeddings=matrix[part].tolist(),
            metadatas=[metadata_of(records[i]) for i in part],
        ))
        if (start // args.batch) % 10 == 0:
            print(f"  upserted {min(start + len(part), len(positions))}/{len(positions)} "
                  f"({time.perf_counter() - started:.0f}s)", file=sys.stderr)
    for start in range(0, len(stale), args.batch):
        retry(lambda: collection.delete(ids=stale[start:start + args.batch]))

    count = collection.count()
    print(f"collection {collection.name}: {count} records "
          f"(upserted {len(positions)}, newly embedded {fresh}, deleted stale {len(stale)})")
    if count != len(records):
        sys.exit(f"count mismatch: chroma {count} vs chunks {len(records)}")


if __name__ == "__main__":
    main()
