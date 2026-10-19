from psycopg_pool import AsyncConnectionPool

from config.settings import KG_LABEL
from crocol.domains.models.graphs import GraphResult

KINDS = (
    "formation", "member", "group", "field", "well", "organization",
    "municipality", "seismic_3d", "fault", "contract", "contract_area",
    "regulation", "document", "person", "institution", "topic", "basin",
)
FUNCTIONS = {
    "resolve": (
        "SELECT entity_id, kind, name, score, mentions, props "
        "FROM kg.resolve(%s::text, %s::text[], %s::integer)",
        ("name", "kinds", "max_rows")),
    "facts": (
        "SELECT direction, rel, other_kind, total, names "
        "FROM kg.facts(%s::bigint, %s::integer)",
        ("entity_id", "max_rows")),
    "entity_documents": (
        "SELECT doc_id, citation, title, collection, scope, chunks, described "
        "FROM kg.entity_documents(%s::bigint, %s::integer)",
        ("entity_id", "max_rows")),
    "evidence_chunks": (
        "SELECT chunk_id, entities_hit, score "
        "FROM kg.evidence_chunks(%s::bigint[], %s::integer, %s::text[], "
        "%s::boolean)",
        ("ids", "max_rows", "collections", "peripheral")),
    "path": (
        "SELECT step, entity_id, kind, name, rel "
        "FROM kg.path(%s::bigint, %s::bigint, %s::integer)",
        ("a", "b", "max_depth")),
    "chunk_texts": (
        "SELECT c.chunk_id, c.doc_id, c.text, c.chunk_type, c.heading_path, "
        "c.page_start, c.page_end, d.citation, d.title, d.source_path, "
        "d.collection, d.doc_type "
        "FROM rag.chunks c JOIN rag.documents d USING (doc_id) "
        "WHERE c.chunk_id = ANY(%s::text[])",
        ("chunk_ids",)),
}
MAX_NAME = 120
MAX_IDS = 50


def ids_of(value: object) -> list[int]:
    """ids of values returns  list of integer"""
    ids = [int(v) for v in value][:MAX_IDS]
    if not ids:
        raise ValueError("no entity ids")
    return ids


def checked(function: str, arguments: dict) -> tuple[str, tuple]:
    """Allowlisted function and validated, ordered parameters."""
    if function not in FUNCTIONS:
        raise ValueError(f"unknown graph function: {function}")

    sql, names = FUNCTIONS[function]
    params = []
    for name in names:
        value = arguments.get(name)
        if name == "name":
            value = str(value).strip()[:MAX_NAME]
            
        elif name == "kinds":
            value = [k for k in value or [] if k in KINDS] or None
            
        elif name in ("max_rows", "max_depth"):
            value = int(value if value is not None else 10)
            
        elif name in ("entity_id", "a", "b"):
            value = int(value)
            
        elif name == "ids":
            value = ids_of(value)
            
        elif name == "collections":
            value = [str(c) for c in value] if value else None
            
        elif name == "peripheral":
            value = bool(value)
            
        elif name == "chunk_ids":
            value = [str(c) for c in value][:MAX_IDS]
            
        params.append(value)

    return sql, tuple(params)


class PgGraphStore:
    """Runs only the allowlisted kg.* functions, with bound parameters."""

    def __init__(self, pool: AsyncConnectionPool) -> None:

        self._pool = pool

    async def run(self, function: str, arguments: dict) -> GraphResult:

        sql, params = checked(function, arguments)
        async with self._pool.connection() as conn:
            cursor = await conn.execute(sql, params)
            columns = [column.name for column in cursor.description]
            records = await cursor.fetchall()

        rows = tuple(dict(zip(columns, record)) for record in records)
        
        return GraphResult(function=function, 
                           rows=rows, 
                           source=KG_LABEL)
