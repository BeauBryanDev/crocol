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
    "well_stats": (
        "SELECT grp, wells, producing, with_depth, without_depth, "
        "unreliable_depth, "
        "mean_depth_ft, mean_depth_m, max_depth_ft, max_depth_m, "
        "mean_fault_km, min_fault_km, matched "
        "FROM geo.well_stats(%s::text, %s::text, %s::text, %s::text, "
        "%s::text[], %s::text, %s::text, %s::text)",
        ("municipality", "field", "department", "operator", "statuses",
         "trajectory", "purpose", "group_by")),
    "well_list": (
        "SELECT well_name, field_name, municipality_name, well_status, "
        "well_trajectory, operator_name, depth_ft, depth_m, depth_reliable, "
        "nearest_fault, fault_km, matched "
        "FROM geo.well_list(%s::text, %s::text, %s::text, %s::text, "
        "%s::text[], %s::text, %s::text, %s::text, %s::real, %s::integer)",
        ("municipality", "field", "department", "operator", "statuses",
         "trajectory", "purpose", "order_by", "max_fault_km", "n")),
    "well_distance": (
        "SELECT well_a_name, field_a, well_b_name, field_b, surface_km, "
        "depth_a_ft, depth_a_m, depth_b_ft, depth_b_m, pay_a_ft, pay_b_ft, "
        "distance_3d_m, distance_3d_ft, note "
        "FROM geo.well_distance(%s::text, %s::text)",
        ("well_a", "well_b")),
}
KINDS = ("well", "field", "municipality")
MAX_NAME = 120
NAMES = ("name", "municipality", "field", "department", "operator",
         "well_a", "well_b")
STATUSES = ("PRODUCTOR", "SIN ESTADO", "TAPONADO Y ABANDONADO", "INYECTOR",
            "SECO", "SUSPENDIDO", "ABANDONADO")
TRAJECTORIES = ("VERTICAL", "DIRECCIONAL", "HORIZONTAL", "TIPO J", "TIPO S")
PURPOSES = ("INYECTOR", "ESTRATIGRAFICO", "PRODUCTOR", "CAPTADOR DE AGUA")
GROUPS = ("field", "municipality", "operator", "field_operator", "status",
          "trajectory", "purpose")
ORDERS = ("name", "depth", "fault")
CHOICES = {
    "trajectory": TRAJECTORIES,
    "purpose": PURPOSES,
    "group_by": GROUPS,
    "order_by": ORDERS,
}
OPTIONAL = ("municipality", "field", "department", "operator", "statuses",
            "trajectory", "purpose", "group_by", "max_fault_km")


def checked_value(name: str, value: object) -> object:

    if value is None and name in OPTIONAL:
        return None
    if name in NAMES:
        return str(value).strip()[:MAX_NAME] or None
    if name == "kind" and value not in KINDS:
        raise ValueError(f"invalid kind: {value}")
    if name in CHOICES:
        if value not in CHOICES[name]:
            raise ValueError(f"invalid {name}: {value}")
        return value
    if name == "statuses":
        statuses = [s for s in value if s in STATUSES]
        if len(statuses) != len(value):
            raise ValueError("invalid status")
        return statuses or None
    if name in ("buffer_km", "km"):
        return float(value)
    if name == "max_fault_km":
        return min(max(float(value), 0.0), 20.0)
    if name == "n":
        return min(max(int(value), 1), 50)
    return value


def checked(function: str, arguments: dict) -> tuple[str, tuple]:
    """Allowlisted function and validated, ordered parameters."""
    if function not in FUNCTIONS:
        raise ValueError(f"unknown spatial function: {function}")

    sql, names = FUNCTIONS[function]
    params = []
    for name in names:
        value = arguments.get(name) if name in OPTIONAL else arguments[name]
        params.append(checked_value(name, value))

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
