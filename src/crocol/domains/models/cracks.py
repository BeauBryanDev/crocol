from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["low", "moderate", "high", "critical"]


@dataclass(frozen=True)
class CrackReport:
    model: str
    threshold: float
    width_px: int
    height_px: int
    tiles: int
    density_pct: float
    fractal_dimension: float
    fractal_r2: float
    crack_count: int
    total_length_px: float
    mean_width_px: float
    max_width_px: float
    severity: Severity
    mean_confidence: float
    ambiguous_pct: float
    elapsed_ms: int
    dominant_angles: tuple[tuple[float, float], ...] = ()
    rose: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CrackAnalysis:
    report: CrackReport
    overlay_webp: bytes = b""
    preview_jpeg: bytes = b""
