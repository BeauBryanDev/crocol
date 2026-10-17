import asyncio
import hashlib
import json

from crocol.application.ports.spatial import SpatialSearch
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.spatials import SpatialCall, SpatialResult

MIN_SCORE = 0.5
MAX_CALLS = 3
MAX_ROWS_SHOWN = 30
AREA_KINDS = ("municipality", "field", "well")
TITLE = "ANH – Banco de Información Petrolera (pozos, sísmica y fallas del VMM)"
TOTALLED = ("fields_in_municipality", "seismic_coverage")
TOTAL_COLUMNS = ("wells", "producing", "items", "length_km", "area_km2")
NOTES = {
    "fields_in_municipality": "Nota: la pertenencia al municipio viene de "
        "los atributos de los pozos; no hay polígonos de municipios ni de "
        "campos.",
    "field_summary": "Nota: conteos según los atributos de los pozos del "
        "campo; los contratos son el atributo CONTRATO de cada pozo.",
    "seismic_coverage": "Nota: la sísmica es geometría de adquisición "
        "(cobertura, año, levantamiento); no implica interpretación del "
        "subsuelo. El área es la envolvente de los pozos ampliada 2 km.",
    "nearest_lines": "Nota: la sísmica es geometría de adquisición; la "
        "distancia es al trazo de la línea.",
    "faults_near": "Nota: trazas del atlas nacional de fallas a escala de "
        "mapa; las distancias son aproximadas.",
    "wells_near_fault": "Nota: trazas del atlas nacional de fallas a escala "
        "de mapa; las distancias son aproximadas.",
}


async def resolve(spatial: SpatialSearch, place: dict) -> tuple[str, str]:
    """Database kind for a mentioned place; ('', name) when not found."""
    name = place["name"]
    result = await spatial.run("resolve_place", {"name": name})
    hits = [row for row in result.rows if row["score"] >= MIN_SCORE]
    preferred = [row for row in hits if row["kind"] == place.get("kind")]
    best = (preferred or hits or [{"kind": ""}])[0]

    return best["kind"], name


def calls_for(kind: str, name: str, intents: set[str]) -> list[SpatialCall]:

    if kind == "fault":
        return [SpatialCall("wells_near_fault", {"name": name, "km": 2})]
    if kind not in AREA_KINDS:
        return []

    calls = []
    if "seismic_coverage" in intents and kind == "well":
        calls.append(SpatialCall("nearest_lines", {"name": name, "n": 5}))
    elif "seismic_coverage" in intents:
        calls.append(SpatialCall("seismic_coverage", {
            "kind": kind, "name": name, "buffer_km": 2}))
    if "faults" in intents:
        calls.append(SpatialCall("faults_near", {
            "kind": kind, "name": name, "km": 5}))
    if not calls and kind == "municipality":
        calls.append(SpatialCall("fields_in_municipality", {"name": name}))
    if not calls and kind == "field":
        calls.append(SpatialCall("field_summary", {"name": name}))

    return calls


def plan_calls(intents: list[str],
               resolved: list[tuple[str, str]]
               ) -> list[SpatialCall]:
    """Deterministic intent-to-function map; no model call."""
    wanted = set(intents)
    calls: list[SpatialCall] = []
    for kind, name in resolved:
        for call in calls_for(kind, name, wanted):
            if call not in calls:
                calls.append(call)

    return calls[:MAX_CALLS]


def row_line(row: dict) -> str:

    parts = []
    for column, value in row.items():
        if value is not None:
            parts.append(f"{column}: {value}")

    return "; ".join(parts)


def total_lines(call: SpatialCall, rows: tuple[dict, ...]) -> list[str]:

    if call.function not in TOTALLED or not rows:
        return []

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row.get("layer", "")), []).append(row)

    lines = []
    for layer, members in groups.items():
        sums = []
        for column in TOTAL_COLUMNS:
            values = [r[column] for r in members if r.get(column) is not None]
            if values:
                sums.append(f"{column}: {round(sum(values), 1)}")
        if sums:
            label = f"TOTAL {layer}".strip()
            lines.append(f"{label} ({len(members)} filas): " + "; ".join(sums))

    return lines


def render(call: SpatialCall, result: SpatialResult) -> str:
    """Evidence text for one database query result."""
    header = (f"Consulta a la base de datos geográfica {result.source} "
              f"(geo.{call.function}): {len(result.rows)} filas.")
    lines = [header]
    for row in result.rows[:MAX_ROWS_SHOWN]:
        lines.append(row_line(row))
    hidden = len(result.rows) - MAX_ROWS_SHOWN
    if hidden > 0:
        lines.append(f"... {hidden} filas más no mostradas.")
    lines.extend(total_lines(call, result.rows))
    if not result.rows:
        lines.append("Sin resultados para este lugar en la base de datos.")
    lines.append(NOTES.get(call.function, ""))

    return "\n".join(line for line in lines if line)


def to_chunk(call: SpatialCall, result: SpatialResult) -> Chunk:

    key = json.dumps([call.function, call.arguments], sort_keys=True)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return Chunk(
        chunk_id=f"spatial-{digest}",
        doc_id=f"spatial-{call.function}",
        text=render(call, result),
        citation=result.source,
        title=TITLE,
        collection="ANH_Spatial",
        doc_type="spatial_query",
        chunk_type="spatial",
        heading_path=f"geo.{call.function}",
    )


async def spatial_search(spatial: SpatialSearch,
                         intents: list[str],
                         places: list[dict]
                         ) -> tuple[list[Chunk], list[SpatialCall]]:
    """Resolve places, run the planned geo.* calls, return evidence."""
    resolved = await asyncio.gather(*[resolve(spatial, p) for p in places])
    calls = plan_calls(intents, list(resolved))
    results = await asyncio.gather(
        *[spatial.run(call.function, call.arguments) for call in calls])

    chunks = []
    for call, result in zip(calls, results):
        chunks.append(to_chunk(call, result))

    return chunks, calls
