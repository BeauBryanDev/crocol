import asyncio
import hashlib
from dataclasses import asdict, dataclass

from crocol.application.ports.production import ProductionSearch
from crocol.domains.models.chunks import Chunk
from crocol.domains.models.productions import ProductionSeries, Trend
from crocol.domains.services.production_trend import (
    STABLE_BAND_PCT,
    VARIABLE_SCATTER_PCT,
    classify,
)

SOURCE = "ANH-Produccion-Fiscalizada-2026"
TITLE = "ANH – Producción fiscalizada de crudo y gas por campo (2025–2026)"
MIN_SCORE = 0.6
MAX_FIELDS = 3
FIELD_KINDS = ("field", "contract_area", "unknown")
LABELS = {
    "decreasing": "DECRECIENTE",
    "increasing": "CRECIENTE",
    "stable": "ESTABLE",
    "variable": "VARIABLE",
    "no_production": "SIN PRODUCCIÓN REPORTADA",
    "insufficient_data": "DATOS INSUFICIENTES",
}
NOTE = (
    "Nota: cifras de producción fiscalizada declaradas por el operador "
    "(ANH, SOLAR); promedios mensuales por día calendario que no descuentan "
    "consumos operacionales ni quemas. La tendencia la calcula Crocol con una "
    f"recta de mínimos cuadrados: un cambio ajustado dentro de "
    f"±{STABLE_BAND_PCT:.0f} % en el periodo es estable, y una dispersión "
    f"de los residuos mayor al {VARIABLE_SCATTER_PCT:.0f} % del promedio es "
    "variable."
)


@dataclass(frozen=True)
class ProductionFound:
    series: tuple[ProductionSeries, ...]
    chunks: tuple[Chunk, ...]


def field_mentions(mentions: list[dict]) -> list[str]:
    """Names that can be fields, in question order, at most MAX_FIELDS."""
    names: list[str] = []
    for item in mentions:
        name = item["name"].strip()
        if item.get("kind", "unknown") in FIELD_KINDS and name not in names:
            names.append(name)
    return names[:MAX_FIELDS]


def number(value: float | None, digits: int) -> str:

    return "—" if value is None else f"{value:,.{digits}f}"


def trend_line(name: str, unit: str, trend: Trend, first: str, last: str,
               digits: int) -> str:

    label = LABELS[trend.label]
    if trend.change_pct is None:
        return f"Tendencia del {name} ({unit}): {label} ({trend.months} meses)."
    return (f"Tendencia del {name} ({unit}), {first} a {last}, {trend.months} "
            f"meses: {label}. Cambio ajustado {trend.change_pct:+.1f} % en el "
            f"periodo ({trend.slope_pct_month:+.2f} %/mes); dispersión "
            f"{trend.scatter_pct:.1f} %. Primer mes {number(trend.first, digits)}, "
            f"último {number(trend.last, digits)}, promedio "
            f"{number(trend.mean, digits)}.")


def render(series: ProductionSeries) -> str:

    group = (f" (contrato que agrupa los campos {', '.join(series.fields)})"
             if series.kind == "contract" else "")
    place = "; ".join(filter(None, [", ".join(series.departments),
                                    ", ".join(series.municipalities)]))
    lines = [
        f"Producción fiscalizada ANH ({SOURCE}) de {series.name}{group}.",
        f"Ubicación: {place}. Operador: {', '.join(series.operators)}.",
        "Unidades: crudo en BPDC (barriles por día calendario, promedio "
        "mensual); gas en MPCPDC (millones de pies cúbicos por día calendario).",
        "Mes | Crudo (BPDC) | Gas (MPCPDC)",
    ]
    for month, oil, gas in zip(series.months, series.oil_bpdc, series.gas_mpcpdc):
        lines.append(f"{month[:7]} | {number(oil, 1)} | {number(gas, 3)}")
    first, last = series.months[0][:7], series.months[-1][:7]
    lines.append(trend_line("crudo", "BPDC", series.oil_trend, first, last, 1))
    lines.append(trend_line("gas", "MPCPDC", series.gas_trend, first, last, 3))
    lines.append(NOTE)
    return "\n".join(lines)


def to_chunk(series: ProductionSeries) -> Chunk:

    digest = hashlib.sha1(",".join(series.fields).encode()).hexdigest()[:12]
    return Chunk(
        chunk_id=f"production-{digest}",
        doc_id=f"production-{digest}",
        text=render(series),
        citation=SOURCE,
        title=TITLE,
        collection="ANH_Production",
        doc_type="production_series",
        chunk_type="production",
        heading_path=f"prod.field_series/{series.name}",
    )


async def one_field(store: ProductionSearch, name: str) -> ProductionSeries | None:

    found = await store.run("resolve_field", {"name": name, "max_rows": 3})
    best = next((r for r in found.rows if r["score"] >= MIN_SCORE), None)
    if best is None:
        return None
    
    keys = list(best["field_keys"])
    series, profile = await asyncio.gather(
        store.run("field_series", {"field_keys": keys}),
        store.run("field_profile", {"field_keys": keys}))
    if not series.rows:
        return None
    
    info = profile.rows[0] if profile.rows else {}
    oil = [r["oil_bpdc"] for r in series.rows]
    gas = [r["gas_mpcpdc"] for r in series.rows]
    
    return ProductionSeries(
        name=best["name"], kind=best["kind"],
        fields=tuple(info.get("fields") or keys),
        months=tuple(r["month_end"] for r in series.rows),
        oil_bpdc=tuple(oil), gas_mpcpdc=tuple(gas),
        oil_trend=classify(oil), gas_trend=classify(gas),
        departments=tuple(info.get("departments") or ()),
        municipalities=tuple(info.get("municipalities") or ()),
        operators=tuple(info.get("operators") or ()),
        source=SOURCE)


async def search_production_by_field(store: ProductionSearch,
                                     mentions: list[dict]
                                     ) -> ProductionFound:
    """Monthly oil and gas series of the fields the question names."""
    names = field_mentions(mentions)
    found = await asyncio.gather(*[one_field(store, n) for n in names])
    series: list[ProductionSeries] = []
    for item in found:
        if item is not None and item.fields not in [s.fields for s in series]:
            series.append(item)
    return ProductionFound(tuple(series), tuple(to_chunk(s) for s in series))


def series_payload(series: ProductionSeries) -> dict:
    """The JSON the frontend chart reads."""
    return {
        "name": series.name, "kind": series.kind,
        "fields": list(series.fields),
        "departments": list(series.departments),
        "municipalities": list(series.municipalities),
        "operators": list(series.operators),
        "units": {"oil": "BPDC", "gas": "MPCPDC"},
        "points": [{"month": m, "oil": o, "gas": g}
                   for m, o, g in zip(series.months,
                                      series.oil_bpdc,
                                      series.gas_mpcpdc)],
        "trends": {"oil": asdict(series.oil_trend),
                   "gas": asdict(series.gas_trend)},
        "source": series.source,
    }
