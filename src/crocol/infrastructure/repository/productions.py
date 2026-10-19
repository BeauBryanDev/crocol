from psycopg_pool import AsyncConnectionPool

from crocol.domains.models.productions import ProductionResult

SOURCE = "ANH-Produccion-Fiscalizada-2026"
FUNCTIONS = {
    "resolve_field": (
        "SELECT kind, name, field_keys, score, has_oil, has_gas "
        "FROM prod.resolve_field(%s::text, %s::integer)",
        ("name", "max_rows")),
    "field_series": (
        "SELECT month_end::text AS month_end, oil_bpdc, gas_mpcpdc "
        "FROM prod.field_series(%s::text[])",
        ("field_keys",)),
    "field_profile": (
        "SELECT fields, departments, municipalities, operators, contracts "
        "FROM prod.field_profile(%s::text[])",
        ("field_keys",)),
}
MAX_NAME = 120
MAX_KEYS = 20


def checked(function: str, arguments: dict) -> tuple[str, tuple]:
    """Allowlisted function and validated, ordered parameters."""
    if function not in FUNCTIONS:
        raise ValueError(f"unknown production function: {function}")

    sql, names = FUNCTIONS[function]
    params = []
    for name in names:
        value = arguments.get(name)
        if name == "name":
            value = str(value).strip()[:MAX_NAME]
        elif name == "max_rows":
            value = int(value if value is not None else 5)
        elif name == "field_keys":
            value = [str(k) for k in value][:MAX_KEYS]
            if not value:
                raise ValueError("no field keys")
        params.append(value)

    return sql, tuple(params)


class PgProductionStore:
    """Runs only the allowlisted prod.* functions, with bound parameters."""

    def __init__(self, pool: AsyncConnectionPool) -> None:

        self._pool = pool

    async def run(self, function: str, arguments: dict) -> ProductionResult:

        sql, params = checked(function, arguments)
        async with self._pool.connection() as conn:
            cursor = await conn.execute(sql, params)
            columns = [column.name for column in cursor.description]
            records = await cursor.fetchall()

        rows = tuple(dict(zip(columns, record)) for record in records)
        
        return ProductionResult(function=function,
                                rows=rows,
                                source=SOURCE)
