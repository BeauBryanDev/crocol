import argparse
import hashlib
import sys
from collections import Counter
from collections.abc import Iterable

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from chunking import PIPELINE_VERSION
from config.settings import get_settings
from rag_inputs import (
    REFERENCES,
    build_chunks,
    build_documents,
    read_inputs,
    validate,
)

DESCRIPTION = (
    "Load corpus_metadata.yaml, manifest.csv, chunks.jsonl and the reference "
    "sections into rag.documents, rag.chunks and rag.references_raw. "
    "Validates first, then loads in one idempotent transaction. "
    "Usage: magdalena/bin/python pipelines/load_rag.py "
    "[--dry-run] [--verify-chroma]"
)
DOC_COLUMNS = (
    "doc_id", "source_path", "collection", "scope", "doc_type", "language",
    "title", "authors", "year", "institution", "venue", "doi", "degree",
    "topics", "formations", "extraction_flags", "legal", "citation",
    "reference", "markdown_path", "sha256", "pages",
)
CHUNK_COLUMNS = (
    "chunk_id", "doc_id", "seq", "chunk_type", "heading_path", "page_start",
    "page_end", "table_id", "article", "clause", "text", "embed_text",
    "lexical_text", "tokens", "content_hash", "pipeline_version",
)
CHROMA_PAGE = 300
SYNC_STATE = """
INSERT INTO ops.sync_state
    (target, pipeline_version, item_count, checksum, synced_at, details)
VALUES (%s, %s, %s, %s, now(), %s)
ON CONFLICT (target) DO UPDATE SET
    pipeline_version = EXCLUDED.pipeline_version,
    item_count = EXCLUDED.item_count,
    checksum = EXCLUDED.checksum,
    synced_at = now(),
    details = EXCLUDED.details
"""
REPORT = """
SELECT d.scope, count(DISTINCT d.doc_id), count(c.chunk_id)
FROM rag.documents d LEFT JOIN rag.chunks c USING (doc_id)
GROUP BY d.scope ORDER BY d.scope
"""


def column_list(columns: Iterable[str]) -> sql.Composed:
    return sql.SQL(", ").join(sql.Identifier(c) for c in columns)


def updates(columns: Iterable[str]) -> sql.Composed:
    parts = []
    for column in columns:
        name = sql.Identifier(column)
        parts.append(sql.SQL("{} = EXCLUDED.{}").format(name, name))
    return sql.SQL(", ").join(parts)


def upsert_documents_sql() -> sql.Composed:
    values = sql.SQL(", ").join(sql.Placeholder(c) for c in DOC_COLUMNS)
    return sql.SQL(
        "INSERT INTO rag.documents ({}) VALUES ({}) "
        "ON CONFLICT (doc_id) DO UPDATE SET {}, loaded_at = now()"
    ).format(column_list(DOC_COLUMNS), values, updates(DOC_COLUMNS[1:]))


def upsert_chunks_sql() -> sql.Composed:
    columns = column_list(CHUNK_COLUMNS)
    return sql.SQL(
        "INSERT INTO rag.chunks ({}) SELECT {} FROM stage_chunks "
        "ON CONFLICT (chunk_id) DO UPDATE SET {}, indexed_at = CASE "
        "WHEN rag.chunks.content_hash = EXCLUDED.content_hash "
        "THEN rag.chunks.indexed_at END"
    ).format(columns, columns, updates(CHUNK_COLUMNS[1:]))


def checksum(ids: Iterable[str]) -> str:
    joined = "\n".join(sorted(ids))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def sync_state(cur: psycopg.Cursor, target: str, ids: set[str],
               details: dict) -> None:
    params = (
        target,
        PIPELINE_VERSION,
        len(ids),
        checksum(ids),
        Jsonb(details),
    )
    cur.execute(SYNC_STATE, params)


def stage_chunks(cur: psycopg.Cursor, chunks: list[tuple]) -> None:
    cur.execute(sql.SQL(
        "CREATE TEMP TABLE stage_chunks ON COMMIT DROP AS "
        "SELECT {} FROM rag.chunks WITH NO DATA"
    ).format(column_list(CHUNK_COLUMNS)))
    copy_sql = sql.SQL("COPY stage_chunks ({}) FROM STDIN").format(
        column_list(CHUNK_COLUMNS))
    with cur.copy(copy_sql) as copy:
        for row in chunks:
            copy.write_row(row)


def load(conn: psycopg.Connection, documents: list[dict],
         chunks: list[tuple], references: list[tuple]) -> int:
    """Upsert everything in one transaction; returns stale chunks deleted."""
    doc_ids = [d["doc_id"] for d in documents]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "DELETE FROM rag.documents WHERE doc_id <> ALL(%s)", (doc_ids,))
        cur.executemany(upsert_documents_sql(), documents)

        stage_chunks(cur, chunks)
        cur.execute(
            "DELETE FROM rag.chunks c WHERE NOT EXISTS (SELECT 1 FROM "
            "stage_chunks s WHERE s.chunk_id = c.chunk_id)")
        deleted = cur.rowcount
        cur.execute(upsert_chunks_sql())

        cur.execute("DELETE FROM rag.references_raw")
        cur.executemany(
            "INSERT INTO rag.references_raw (doc_id, text) VALUES (%s, %s)",
            references)

        details = {
            "documents": len(documents),
            "references": len(references),
        }
        sync_state(cur, "rag", {row[0] for row in chunks}, details)
    return deleted


def chroma_ids() -> set[str]:
    from crocol.infrastructure.vectors.chroma_store import chroma_client

    name = get_settings().collection_name
    collection = chroma_client().get_collection(name)
    ids: set[str] = set()
    offset = 0
    while True:
        result = collection.get(include=[], limit=CHROMA_PAGE, offset=offset)
        batch = result.get("ids") or []
        ids.update(batch)
        if len(batch) < CHROMA_PAGE:
            return ids
        offset += CHROMA_PAGE


def verify_chroma(conn: psycopg.Connection) -> bool:
    remote = chroma_ids()
    rows = conn.execute("SELECT chunk_id FROM rag.chunks")
    local = {row[0] for row in rows}
    if remote != local:
        print(f"chroma mismatch: only Postgres {len(local - remote)}, "
              f"only Chroma {len(remote - local)}", file=sys.stderr)
        return False

    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE rag.chunks SET indexed_at = now() "
            "WHERE indexed_at IS NULL")
        details = {"collection": get_settings().collection_name}
        sync_state(cur, "chroma", remote, details)
    print(f"chroma verified: {len(remote)} ids match rag.chunks")
    return True


def report(conn: psycopg.Connection) -> None:
    for scope, docs, chunks in conn.execute(REPORT):
        print(f"  {scope:<10} documents {docs:>3}  chunks {chunks:>5}")
    refs = conn.execute("SELECT count(*) FROM rag.references_raw").fetchone()
    print(f"  references_raw {refs[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-chroma", action="store_true")
    args = parser.parse_args()

    metadata, manifest, records, embed_index, references = read_inputs()
    errors = validate(metadata, manifest, records, embed_index, references)
    if errors:
        print("validation failed:", *errors, sep="\n  ", file=sys.stderr)
        sys.exit(1)

    documents = build_documents(metadata, manifest)
    chunks = build_chunks(records, embed_index)
    reference_rows = []
    for name, doc_id in references.items():
        text = (REFERENCES / name).read_text(encoding="utf-8")
        reference_rows.append((doc_id, text))
    scopes = dict(Counter(d["scope"] for d in documents))
    print(f"validated: documents {len(documents)} {scopes}, "
          f"chunks {len(chunks)}, references {len(reference_rows)}")
    if args.dry_run:
        return

    dsn = get_settings().pg_dsn
    if dsn is None:
        sys.exit("PG_DSN is not set in .env")
    with psycopg.connect(dsn.get_secret_value()) as conn:
        deleted = load(conn, documents, chunks, reference_rows)
        print(f"loaded (stale chunks deleted: {deleted})")
        report(conn)
        if args.verify_chroma and not verify_chroma(conn):
            sys.exit(1)


if __name__ == "__main__":
    main()
