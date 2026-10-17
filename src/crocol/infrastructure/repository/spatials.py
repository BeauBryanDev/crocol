from psycopg_pool import AsyncConnectionPool

from crocol.domains.models.spatials import SpatialResult

SOURCE = "ANH-Informacion-Petrolera-2026"
FUNCTIONS = {
    "resolve_place": (
        "SELECT kind, name, score FROM geo.resolve_place(%s::text)",
        ("name",)),
    "fields_in_municipality": (
        "SELECT field, wells, producing, municipality_name, department "
        "FROM geo.fields_in_municipality(%s::text)",
        ("name",)),
    "field_summary": (
        "SELECT dimension, value, wells FROM geo.field_summary(%s::text)",
        ("name",)),
    "seismic_coverage": (
        "SELECT layer, decade, survey, items, length_km, area_km2 "
        "FROM geo.seismic_coverage(%s::text, %s::text, %s::real)",
        ("kind", "name", "buffer_km")),
    "faults_near": (
        "SELECT fault_name, fault_type, distance_km, length_km "
        "FROM geo.faults_near(%s::text, %s::text, %s::real)",
        ("kind", "name", "km")),
    "wells_near_fault": (
        "SELECT well_name, field, status, distance_km, fault_name "
        "FROM geo.wells_near_fault(%s::text, %s::real)",
        ("name", "km")),
    "locate": (
        "SELECT kind, name, geojson, source FROM geo.locate(%s::text)",
        ("name",)),
    "nearest_lines": (
        "SELECT survey, line_name, acq_year, distance_km, well_name "
        "FROM geo.nearest_lines(%s::text, %s::integer)",
        ("name", "n")),
}
KINDS = ("well", "field", "municipality")
MAX_NAME = 120


def checked(function: str, arguments: dict) -> tuple[str, tuple]:
    """Allowlisted function and validated, ordered parameters."""
    if function not in FUNCTIONS:
        raise ValueError(f"unknown spatial function: {function}")

    sql, names = FUNCTIONS[function]
    params = []
    for name in names:
        value = arguments[name]
        if name == "name":
            value = str(value).strip()[:MAX_NAME]
        elif name == "kind" and value not in KINDS:
            raise ValueError(f"invalid kind: {value}")
        elif name in ("buffer_km", "km"):
            value = float(value)
        elif name == "n":
            value = int(value)
        params.append(value)

    return sql, tuple(params)


class PgSpatialStore:
    """Runs only the allowlisted geo.* functions, with bound parameters."""

    def __init__(self, pool: AsyncConnectionPool) -> None:

        self._pool = pool

    async def run(self, function: str, arguments: dict) -> SpatialResult:

        sql, params = checked(function, arguments)
        async with self._pool.connection() as conn:
            cursor = await conn.execute(sql, params)
            columns = [column.name for column in cursor.description]
            records = await cursor.fetchall()

        rows = []
        for record in records:
            rows.append(dict(zip(columns, record)))

        return SpatialResult(function=function, rows=tuple(rows),
                             source=SOURCE)
