import argparse
import hashlib
import sys
import time
from collections import Counter

import psycopg
from psycopg.types.json import Jsonb

from config.settings import ROOT, get_settings
from graph_entities import GraphDraft, build_draft
from graph_linking import (
    build_gazetteer,
    document_priors,
    link_chunks,
    read_chunks,
    write_review,
)

DESCRIPTION = (
    "Build the Crocol knowledge graph (kg.*) from core.*, rag.documents, "
    "kg/formations.yaml and the chunk texts. Rebuilt from scratch in one "
    "transaction. Usage: magdalena/bin/python pipelines/build_graph.py "
    "[--step entities|mentions|derived|all] [--sample N] [--dry-run]"
)
GRAPH_VERSION = "kg-v1"
REVIEW = ROOT / "docs" / "kg_mentions_review.csv"
CO_MENTION_MIN_CONFIDENCE = 0.7
CO_MENTION_MAX_PER_CHUNK = 30
CO_MENTION_TOP = 50

TRUNCATE_GRAPH = "TRUNCATE kg.entities RESTART IDENTITY CASCADE"
STAGE_ALIASES = "CREATE TEMP TABLE stage_aliases (alias text, entity_id bigint) ON COMMIT DROP"
INSERT_ALIASES = """
INSERT INTO kg.aliases (alias_key, alias, entity_id)
SELECT core.name_key(alias), alias, entity_id FROM stage_aliases
WHERE core.name_key(alias) <> ''
ON CONFLICT DO NOTHING
"""
DELETE_DERIVED = "DELETE FROM kg.edges WHERE source = 'derived'"
INSERT_CO_MENTIONED = """
WITH eligible AS (
    SELECT chunk_id FROM kg.mentions
    WHERE confidence >= %(conf)s
    GROUP BY chunk_id HAVING count(*) BETWEEN 2 AND %(per_chunk)s
), pairs AS (
    SELECT a.entity_id AS src, b.entity_id AS dst, count(*) AS shared
    FROM kg.mentions a
    JOIN kg.mentions b ON b.chunk_id = a.chunk_id AND b.entity_id > a.entity_id
    JOIN eligible e ON e.chunk_id = a.chunk_id
    WHERE a.confidence >= %(conf)s AND b.confidence >= %(conf)s
    GROUP BY 1, 2
    HAVING count(*) >= 2
), ranked AS (
    SELECT src, dst, shared,
           row_number() OVER (PARTITION BY src ORDER BY shared DESC, dst) AS rs,
           row_number() OVER (PARTITION BY dst ORDER BY shared DESC, src) AS rd
    FROM pairs
)
INSERT INTO kg.edges (src, rel, dst, weight, source, evidence)
SELECT src, 'CO_MENTIONED', dst, shared, 'derived',
       jsonb_build_object('shared_chunks', shared)
FROM ranked WHERE rs <= %(top)s OR rd <= %(top)s
"""
SYNC_STATE = """
INSERT INTO ops.sync_state
    (target, pipeline_version, item_count, checksum, synced_at, details)
VALUES ('kg', %s, %s, %s, now(), %s)
ON CONFLICT (target) DO UPDATE SET
    pipeline_version = EXCLUDED.pipeline_version,
    item_count = EXCLUDED.item_count,
    checksum = EXCLUDED.checksum,
    synced_at = now(),
    details = EXCLUDED.details
"""
COUNTS = {
    "entities": "SELECT count(*) FROM kg.entities",
    "aliases": "SELECT count(*) FROM kg.aliases",
    "edges": "SELECT count(*) FROM kg.edges",
    "mentions": "SELECT count(*) FROM kg.mentions",
    "linked_chunks": "SELECT count(DISTINCT chunk_id) FROM kg.mentions",
}
BY_KIND = "SELECT kind, count(*) FROM kg.entities GROUP BY 1 ORDER BY 2 DESC"
BY_REL = "SELECT rel, count(*) FROM kg.edges GROUP BY 1 ORDER BY 2 DESC"
MENTIONS_BY_KIND = """
SELECT e.kind, count(*), count(DISTINCT m.entity_id)
FROM kg.mentions m JOIN kg.entities e USING (entity_id)
GROUP BY 1 ORDER BY 2 DESC
"""


def write_entities(conn: psycopg.Connection, draft: GraphDraft) -> dict:

    conn.execute(TRUNCATE_GRAPH)
    with conn.cursor().copy(
            "COPY kg.entities (kind, key, name, ref_table, ref_id, props) "
            "FROM STDIN") as copy:
        for row in draft.entities.values():
            copy.write_row((row.kind, row.key, row.name, row.ref_table,
                            row.ref_id, Jsonb(row.props)))

    ids = {(kind, key): entity_id for entity_id, kind, key in
           conn.execute("SELECT entity_id, kind, key FROM kg.entities")}

    conn.execute(STAGE_ALIASES)
    with conn.cursor().copy("COPY stage_aliases FROM STDIN") as copy:
        for ident, row in draft.entities.items():
            for alias in dict.fromkeys([row.name, *row.aliases]):
                copy.write_row((alias, ids[ident]))
    conn.execute(INSERT_ALIASES)

    edges = {}
    for edge in draft.edges:
        key = (ids[edge.src], edge.rel, ids[edge.dst])
        edges.setdefault(key, edge)
    with conn.cursor().copy(
            "COPY kg.edges (src, rel, dst, source, evidence) FROM STDIN") as copy:
        for (src, rel, dst), edge in edges.items():
            copy.write_row((src, rel, dst, edge.source, Jsonb(edge.evidence)))
    return {"edges_written": len(edges)}


def write_mentions(conn: psycopg.Connection, sample: int,
                   review: bool) -> dict:

    started = time.perf_counter()
    gazetteer = build_gazetteer(conn)
    chunks = read_chunks(conn, sample)
    linked = link_chunks(gazetteer, chunks, document_priors(conn))
    notes = {
        "gazetteer_forms": gazetteer.forms,
        "chunks_read": len(chunks),
        "mentions_found": len(linked.rows),
        "by_rule": linked.by_rule,
        "linking_s": round(time.perf_counter() - started, 1),
    }
    if review:
        write_review(REVIEW, linked.review)
        notes["review_rows"] = len(linked.review)
    if sample:
        return notes

    conn.execute("TRUNCATE kg.mentions")
    with conn.cursor().copy(
            "COPY kg.mentions (chunk_id, entity_id, hits, confidence, rule) "
            "FROM STDIN") as copy:
        for row in linked.rows:
            copy.write_row(row)
    return notes


def write_derived(conn: psycopg.Connection) -> dict:

    conn.execute(DELETE_DERIVED)
    cursor = conn.execute(INSERT_CO_MENTIONED, {
        "conf": CO_MENTION_MIN_CONFIDENCE,
        "per_chunk": CO_MENTION_MAX_PER_CHUNK,
        "top": CO_MENTION_TOP,
    })
    return {"co_mentioned": cursor.rowcount}


def record_sync(conn: psycopg.Connection, counts: dict) -> None:

    digest = hashlib.sha256(repr(sorted(counts.items())).encode()).hexdigest()
    conn.execute(SYNC_STATE, (GRAPH_VERSION, counts["entities"], digest,
                              Jsonb(counts)))


def report(conn: psycopg.Connection) -> dict:

    counts = {name: conn.execute(query).fetchone()[0]
              for name, query in COUNTS.items()}
    print("entities by kind:", dict(conn.execute(BY_KIND).fetchall()))
    print("edges by rel:", dict(conn.execute(BY_REL).fetchall()))
    print("mentions by kind (links, entities):",
          {k: (n, e) for k, n, e in conn.execute(MENTIONS_BY_KIND)})
    return counts


def run(args: argparse.Namespace) -> None:

    dsn = get_settings().pg_dsn
    if dsn is None:
        sys.exit("PG_DSN is not set in .env")

    started = time.perf_counter()
    notes: dict = {}
    with psycopg.connect(dsn.get_secret_value()) as conn:
        draft, notes = build_draft(conn)
        kinds = Counter(kind for kind, _ in draft.entities)
        notes["draft_entities"] = dict(kinds.most_common())
        notes["draft_edges"] = len(draft.edges)
        if args.dry_run:
            print_notes(notes, started, "dry-run")
            return

        with conn.transaction():
            if args.step in ("entities", "all"):
                notes.update(write_entities(conn, draft))
            if args.step in ("mentions", "all"):
                notes.update(write_mentions(conn, args.sample,
                                            review=args.step == "all"
                                            or args.review))
            if args.sample:
                print_notes(notes, started, f"sample {args.sample}")
                raise Rollback()
            if args.step in ("derived", "mentions", "all"):
                notes.update(write_derived(conn))
            counts = report(conn)
            record_sync(conn, counts)
            notes.update(counts)

    print_notes(notes, started, args.step)


class Rollback(Exception):
    pass


def print_notes(notes: dict, started: float, label: str) -> None:

    print(f"step {label} done in {time.perf_counter() - started:.1f} s")
    for name, value in notes.items():
        print(f"  {name:<22} {value}")


def main() -> None:

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--step", default="all",
                        choices=["entities", "mentions", "derived", "all"])
    parser.add_argument("--sample", type=int, default=0,
                        help="link N random chunks, measure only, save nothing")
    parser.add_argument("--review", action="store_true",
                        help="write docs/kg_mentions_review.csv")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the entity draft only, no writes")
    try:
        run(parser.parse_args())
    except Rollback:
        pass


if __name__ == "__main__":
    main()
