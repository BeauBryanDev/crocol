from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductionResult:
    function: str
    rows: tuple[dict, ...] = ()
    source: str = ""


@dataclass(frozen=True)
class Trend:
    label: str
    months: int
    first: float | None = None
    last: float | None = None
    mean: float | None = None
    change_pct: float | None = None
    slope_pct_month: float | None = None
    scatter_pct: float | None = None


@dataclass(frozen=True)
class ProductionSeries:
    name: str
    kind: str
    fields: tuple[str, ...]
    months: tuple[str, ...]
    oil_bpdc: tuple[float | None, ...]
    gas_mpcpdc: tuple[float | None, ...]
    oil_trend: Trend
    gas_trend: Trend
    departments: tuple[str, ...] = ()
    municipalities: tuple[str, ...] = ()
    operators: tuple[str, ...] = ()
    source: str = ""
    extra: dict = field(default_factory=dict)
