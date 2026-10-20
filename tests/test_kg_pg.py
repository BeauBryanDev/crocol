import time

import psycopg
import pytest

from config.settings import get_settings
from crocol.infrastructure.repository.graphs import checked

pytestmark = pytest.mark.integration
OPTIONS = "-c default_transaction_read_only=on -c statement_timeout=5s"
FAST_MS = 200


def connect() -> psycopg.Connection | None:

    dsn = get_settings().pg_dsn
    if dsn is None:
        return None
    try:
        return psycopg.connect(dsn.get_secret_value(), options=OPTIONS,
                               autocommit=True, connect_timeout=2)
    except psycopg.OperationalError:
        return None


@pytest.fixture(scope="module")
def conn() -> psycopg.Connection:

    connection = connect()
    if connection is None:
        pytest.skip("vmm-postgis is not reachable")
    built = connection.execute(
        "SELECT to_regclass('kg.entities') IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM kg.entities)").fetchone()[0]
    if not built:
        pytest.skip("knowledge graph is not built")
    yield connection
    connection.close()


def run(conn: psycopg.Connection, function: str, **arguments: object
        ) -> tuple[list[dict], float]:

    sql, params = checked(function, arguments)
    started = time.perf_counter()
    cursor = conn.execute(sql, params)
    columns = [c.name for c in cursor.description]
    found = [dict(zip(columns, r)) for r in cursor.fetchall()]
    return found, (time.perf_counter() - started) * 1000


def entity(conn: psycopg.Connection, name: str, kind: str) -> int:

    found, _ = run(conn, "resolve", name=name, kinds=[kind], max_rows=1)
    assert found, f"{kind} {name} not resolved"
    return found[0]["entity_id"]


def test_every_vmm_well_is_an_entity(conn: psycopg.Connection) -> None:

    wells, entities = conn.execute(
        "SELECT (SELECT count(*) FROM core.wells), "
        "(SELECT count(*) FROM kg.entities WHERE kind = 'well')").fetchone()
    assert wells == entities == 10705


def test_resolve_exact_name_first(conn: psycopg.Connection) -> None:

    found, ms = run(conn, "resolve", name="La Luna", kinds=None, max_rows=5)
    assert found[0]["name"] == "La Luna"
    assert found[0]["kind"] == "formation"
    assert found[0]["score"] == 1.0
    assert ms < FAST_MS


def test_stratigraphy_is_curated(conn: psycopg.Connection) -> None:

    facts, ms = run(conn, "facts", entity_id=entity(conn, "La Luna",
                                                      "formation"),
                    max_rows=20)
    by_rel = {(f["direction"], f["rel"]): f["names"] for f in facts}
    assert sorted(by_rel[("in", "PART_OF")]) == ["Galembo", "Pujamana",
                                                 "Salada"]
    assert by_rel[("out", "OVERLIES")] == ["Simití"]
    assert by_rel[("in", "OVERLIES")] == ["Umir"]
    assert ms < FAST_MS


def test_well_attributes_become_edges(conn: psycopg.Connection) -> None:

    well = entity(conn, "INFANTAS-1613", "well")
    facts, _ = run(conn, "facts", entity_id=well, max_rows=20)
    rels = {f["rel"] for f in facts if f["direction"] == "out"}
    assert {"IN_FIELD", "LOCATED_IN", "OPERATED_BY"} <= rels


def test_evidence_chunks_respect_scope(conn: psycopg.Connection) -> None:

    galembo = entity(conn, "Galembo", "member")
    core, ms = run(conn, "evidence_chunks", ids=[galembo], max_rows=20,
                   collections=["VMM_Basin"], peripheral=False)
    assert core and ms < FAST_MS
    ids = [r["chunk_id"] for r in core]
    scopes = conn.execute(
        "SELECT DISTINCT d.collection, d.scope FROM rag.chunks c "
        "JOIN rag.documents d USING (doc_id) WHERE c.chunk_id = ANY(%s)",
        (ids,)).fetchall()
    assert scopes == [("VMM_Basin", "core")]


def test_path_and_neighbors_are_fast(conn: psycopg.Connection) -> None:

    well = entity(conn, "INFANTAS-1613", "well")
    ecopetrol = entity(conn, "Ecopetrol", "organization")
    path, ms = run(conn, "path", a=well, b=ecopetrol, max_depth=3)
    assert [p["rel"] for p in path] == [None, "OPERATED_BY"]
    assert ms < FAST_MS

    cira = entity(conn, "La Cira Infantas", "field")
    sql = "SELECT count(*) FROM kg.neighbors(%s::bigint[], 2)"
    started = time.perf_counter()
    count = conn.execute(sql, ([cira],)).fetchone()[0]
    assert count == 200
    assert (time.perf_counter() - started) * 1000 < FAST_MS


def test_mentions_never_point_at_unlinked_kinds(
        conn: psycopg.Connection) -> None:

    kinds = {k for (k,) in conn.execute(
        "SELECT DISTINCT e.kind FROM kg.mentions m "
        "JOIN kg.entities e USING (entity_id)")}
    assert not kinds & {"document", "person", "topic", "institution",
                        "regulation", "basin", "contract"}


def test_graph_store_rejects_unknown_functions() -> None:

    with pytest.raises(ValueError):
        checked("drop_everything", {})
    sql, params = checked("resolve", {"name": "x" * 500,
                                      "kinds": ["well", "bogus"],
                                      "max_rows": 3})
    assert params == ("x" * 120, ["well"], 3)
