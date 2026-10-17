from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

LOG_COLUMNS = (
    "trace_id", "language", "mode", "corpus_scope", "chunk_policy",
    "status", "attempts", "llm_calls", "tokens_in", "tokens_out",
    "latency_ms", "cross_family", "verification", "conflicts", "trace",
    "pipeline_version", "app_version",
)
JSON_COLUMNS = ("verification", "conflicts", "trace")
INSERT_LOG = (
    f"INSERT INTO ops.query_log ({', '.join(LOG_COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(LOG_COLUMNS))})"
)
INSERT_CHUNK = """
INSERT INTO ops.query_chunks
    (trace_id, stage, chunk_id, channel, rank, score, relevant)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT DO NOTHING
"""
SELECT_LOG = f"""
SELECT created_at, {', '.join(LOG_COLUMNS)}
FROM ops.query_log WHERE trace_id = %s
"""
SELECT_CHUNKS = """
SELECT stage, chunk_id, channel, rank, score, relevant
FROM ops.query_chunks WHERE trace_id = %s
ORDER BY stage, rank NULLS LAST
"""
CHUNK_FIELDS = ("stage", "chunk_id", "channel", "rank", "score", "relevant")
SELECT_TODAY = """
SELECT count(*), coalesce(sum(coalesce(tokens_in, 0)
                              + coalesce(tokens_out, 0)), 0)
FROM ops.query_log
WHERE created_at >= date_trunc('day', now() AT TIME ZONE 'UTC')
                    AT TIME ZONE 'UTC'
"""


def log_params(record: dict) -> list:

    params = []
    for column in LOG_COLUMNS:
        value = record.get(column)
        params.append(Jsonb(value) if column in JSON_COLUMNS else value)

    return params


def chunk_params(record: dict) -> list[tuple]:

    rows = []
    for item in record.get("chunks", []):
        rows.append((
            record["trace_id"],
            item["stage"],
            item["chunk_id"],
            item.get("channel"),
            item.get("rank"),
            item.get("score"),
            item.get("relevant"),
        ))

    return rows


class PgTraceStore:
    """Writes one finished trace; the session is read-only by default."""

    def __init__(self, pool: AsyncConnectionPool) -> None:

        self._pool = pool

    async def save(self, record: dict) -> None:

        async with self._pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ WRITE")
                await conn.execute(INSERT_LOG, log_params(record))
                async with conn.cursor() as cursor:
                    await cursor.executemany(INSERT_CHUNK,
                                             chunk_params(record))

    async def get(self, trace_id: str) -> dict | None:

        async with self._pool.connection() as conn:
            cursor = await conn.execute(SELECT_LOG, (trace_id,))
            row = await cursor.fetchone()
            if row is None:
                return None

            cursor = await conn.execute(SELECT_CHUNKS, (trace_id,))
            chunk_rows = await cursor.fetchall()

        record = dict(zip(("created_at", *LOG_COLUMNS), row))
        record["trace_id"] = str(record["trace_id"])
        record["created_at"] = record["created_at"].isoformat()
        record["chunks"] = [dict(zip(CHUNK_FIELDS, r)) for r in chunk_rows]

        return record

    async def today_totals(self) -> tuple[int, int]:
        """Questions and tokens logged since midnight UTC."""
        async with self._pool.connection() as conn:
            cursor = await conn.execute(SELECT_TODAY)
            questions, tokens = await cursor.fetchone()
        return int(questions), int(tokens)
