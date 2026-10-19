from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["low", "moderate", "high", "critical"]

## Computer Vision model class from my CNN MobileNetV3-U-Net Segmentation model
@dataclass(frozen=True)
class CrackReport:
    model: str = field(default="")
    threshold: float = field(default=0.5)
    width_px: int = field(default=0)
    height_px: int = field(default=0)
    tiles: int = field(default=0)
    density_pct: float = field(default=0.0)
    fractal_dimension: float = field(default=0.0)
    fractal_r2: float = field(default=0.0)
    crack_count: int = field(default=0)
    total_length_px: float = field(default=0.0)
    mean_width_px: float = field(default=0.0)
    max_width_px: float = field(default=0.0)
    severity: Severity = field(default="low")
    mean_confidence: float = field(default=0.0)
    ambiguous_pct: float = field(default=0.0)
    elapsed_ms: int = field(default=0)
    dominant_angles: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    rose: tuple[float, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CrackAnalysis:
    report: CrackReport = field(default_factory=CrackReport)
    overlay_webp: bytes = field(default=b"")
    mask_webp: bytes = field(default=b"")
    preview_jpeg: bytes = field(default=b"")
