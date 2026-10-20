import hashlib
import uuid

import psycopg
import pytest

from config.settings import get_settings
from crocol.infrastructure.repository.documents import PgDocumentStore
from crocol.infrastructure.repository.pool import build_pool
from crocol.infrastructure.repository.spatials import PgSpatialStore
from crocol.infrastructure.repository.traces import PgTraceStore

pytestmark = [pytest.mark.integration, pytest.mark.anyio]
SOURCE = "feart-11-1146126.pdf"


def database_up() -> bool:
    dsn = get_settings().pg_dsn
    if dsn is None:
        return False
    try:
        with psycopg.connect(dsn.get_secret_value(), connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


if not database_up():
    pytest.skip("vmm-postgis is not reachable", allow_module_level=True)


def record(trace_id: str) -> dict:
    return {
        "trace_id": trace_id, "language": "es", "mode": "quick",
        "corpus_scope": "core", "chunk_policy": "prose_tables",
        "status": "answered", "attempts": 0, "llm_calls": 4,
        "tokens_in": 10, "tokens_out": 5, "latency_ms": 123,
        "cross_family": True, "verification": {"verified": True},
        "conflicts": [], "trace": [{"node": "analyze", "status": "ok"}],
        "pipeline_version": "chunk-v1", "app_version": "test",
        "chunks": [{"stage": "cited", "chunk_id": "abc", "rank": 1,
                    "relevant": True}],
    }


async def delete_trace(trace_id: str) -> None:
    dsn = get_settings().pg_dsn.get_secret_value()
    async with await psycopg.AsyncConnection.connect(dsn) as conn:
        await conn.execute("DELETE FROM ops.query_log WHERE trace_id = %s",
                           (trace_id,))


async def test_documents_come_from_rag_documents() -> None:
    doc_id = hashlib.sha1(SOURCE.encode("utf-8")).hexdigest()[:12]
    async with build_pool() as pool:
        documents = await PgDocumentStore(pool).get_many([doc_id, "nope"])
    assert list(documents) == [doc_id]
    assert "Pastor-Chacón" in documents[doc_id].reference


async def test_trace_round_trip() -> None:
    trace_id = str(uuid.uuid4())
    try:
        async with build_pool() as pool:
            store = PgTraceStore(pool)
            await store.save(record(trace_id))
            saved = await store.get(trace_id)
        assert saved["status"] == "answered"
        assert saved["trace"][0]["node"] == "analyze"
        assert saved["chunks"][0]["chunk_id"] == "abc"
    finally:
        await delete_trace(trace_id)


async def test_pooled_sessions_are_read_only() -> None:
    async with build_pool() as pool:
        async with pool.connection() as conn:
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                await conn.execute(
                    "UPDATE rag.documents SET title = title WHERE false")


async def test_spatial_store_runs_allowlisted_functions() -> None:
    async with build_pool() as pool:
        store = PgSpatialStore(pool)
        result = await store.run("fields_in_municipality",
                                 {"name": "barrancabermeja"})
    assert sum(row["wells"] for row in result.rows) == 3687
    assert result.source == "ANH-Informacion-Petrolera-2026"


@pytest.mark.parametrize(
    ("function", "arguments"),
    [
        ("resolve_place", {"name": "yondo"}),
        ("fields_in_municipality", {"name": "Puerto Wilches"}),
        ("field_summary", {"name": "Casabe"}),
        ("seismic_coverage", {"kind": "field", "name": "Casabe",
                              "buffer_km": 2}),
        ("faults_near", {"kind": "field", "name": "La Cira", "km": 5}),
        ("wells_near_fault", {"name": "Falla de Cimitarra", "km": 2}),
        ("nearest_lines", {"name": "CASABE-1", "n": 3}),
    ],
)
async def test_every_allowlisted_function_runs(function: str,
                                               arguments: dict) -> None:
    async with build_pool() as pool:
        result = await PgSpatialStore(pool).run(function, arguments)
    assert result.rows
