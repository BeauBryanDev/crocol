import math
from bisect import bisect_right

import numpy as np
from scipy import ndimage

ROSE_BINS = 18
BIN_DEG = 180 / ROSE_BINS
DOMINANT_MIN_SHARE = 0.10
MAX_DOMINANT = 3
DENSITY_LEVELS = (1.0, 3.0, 7.0)
FRACTAL_LEVELS = (1.20, 1.35, 1.50)
SEVERITIES = ("low", "moderate", "high", "critical")
EIGHT_CONNECTED = np.ones((3, 3), dtype=bool)


def square_crop(mask: np.ndarray) -> np.ndarray:
    """The cracks' bounding box, zero-padded to a square."""
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    crop = mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
    side = max(crop.shape)
    square = np.zeros((side, side), dtype=bool)
    square[:crop.shape[0], :crop.shape[1]] = crop
    return square


def fractal_dimension(mask: np.ndarray) -> tuple[float, float]:
    """Box-counting dimension and the R² of the log-log fit."""
    if not mask.any():
        return 0.0, 0.0

    square = square_crop(mask)
    side = square.shape[0]
    sizes, counts = [], []
    size = 2
    while size <= side // 4:
        cells = side // size * size
        blocks = square[:cells, :cells].reshape(
            cells // size, size, cells // size, size)
        occupied = int(blocks.any(axis=(1, 3)).sum())
        if occupied:
            sizes.append(size)
            counts.append(occupied)
        size *= 2

    if len(sizes) < 3:
        return 0.0, 0.0

    x = np.log(1.0 / np.asarray(sizes, dtype=float))
    y = np.log(np.asarray(counts, dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    total = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((residual ** 2).sum()) / total if total else 0.0
    return float(slope), r2


def ridge_of(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Distance transform and its local maxima: an approximate centerline."""
    distance = ndimage.distance_transform_edt(mask)
    peaks = distance >= ndimage.maximum_filter(distance, size=3)
    return distance, mask & peaks & (distance > 0)


def principal_angle(rows: np.ndarray,
                    cols: np.ndarray
                    ) -> tuple[float, float]:
    """Direction of one crack (0-180°, counterclockwise) and elongation."""
    x = cols.astype(float) - cols.mean()
    y = -(rows.astype(float) - rows.mean())
    covariance = np.cov(np.vstack([x, y]))
    values, vectors = np.linalg.eigh(covariance)
    if values[-1] <= 0:
        return 0.0, 0.0

    vx, vy = vectors[:, -1]
    angle = math.degrees(math.atan2(vy, vx)) % 180.0
    elongation = 1.0 - max(values[0], 0.0) / values[-1]
    return angle, elongation


def component_angles(labels: np.ndarray, count: int,
                     ridge: np.ndarray) -> list[tuple[float, float]]:
    """(angle, weight) per crack; weight = centerline length x elongation."""
    lengths = np.bincount(labels[ridge], minlength=count + 1)
    found = []
    for index, region in enumerate(ndimage.find_objects(labels), start=1):
        if region is None:
            continue
        rows, cols = np.nonzero(labels[region] == index)
        if len(rows) < 3:
            continue
        angle, elongation = principal_angle(rows + region[0].start,
                                            cols + region[1].start)
        weight = float(lengths[index]) * elongation
        if weight > 0:
            found.append((angle, weight))
    return found


def rose_of(angles: list[tuple[float, float]]) -> list[float]:

    histogram = np.zeros(ROSE_BINS)
    for angle, weight in angles:
        histogram[int(angle // BIN_DEG) % ROSE_BINS] += weight
    total = histogram.sum()
    return (histogram / total).round(4).tolist() if total else [0.0] * ROSE_BINS


def mean_axial(angles: list[tuple[float, float]]) -> float:
    """Weighted mean of axial angles (doubled-angle circular mean)."""
    sx = sum(w * math.cos(math.radians(2 * a)) for a, w in angles)
    sy = sum(w * math.sin(math.radians(2 * a)) for a, w in angles)
    return (math.degrees(math.atan2(sy, sx)) / 2) % 180.0


def dominant_angles(angles: list[tuple[float, float]],
                    rose: list[float]) -> list[tuple[float, float]]:
    """Up to 3 peaks of the rose, each as (mean angle, share)."""
    peaks = []
    for b, share in enumerate(rose):
        left = rose[(b - 1) % ROSE_BINS]
        right = rose[(b + 1) % ROSE_BINS]
        if share >= DOMINANT_MIN_SHARE and share >= left and share > right:
            peaks.append((share, b))

    found = []
    for _, b in sorted(peaks, reverse=True)[:MAX_DOMINANT]:
        near = {(b - 1) % ROSE_BINS, b, (b + 1) % ROSE_BINS}
        members = [(a, w) for a, w in angles
                   if int(a // BIN_DEG) % ROSE_BINS in near]
        share = sum(rose[i] for i in near)
        found.append((round(mean_axial(members), 1), round(share, 3)))
    return found


def level_of(value: float, edges: tuple[float, ...]) -> int:

    return bisect_right(edges, value)


def severity_of(density_pct: float, fractal: float) -> str:
    """Heuristic class; not an engineering standard."""
    density_level = level_of(density_pct, DENSITY_LEVELS)
    fractal_level = level_of(fractal, FRACTAL_LEVELS)
    return SEVERITIES[math.ceil((density_level + fractal_level) / 2)]


def measure(mask: np.ndarray) -> dict:
    """All geometric metrics of a binary crack mask, in pixels."""
    density = float(mask.mean() * 100) if mask.size else 0.0
    fractal, r2 = fractal_dimension(mask)
    labels, count = ndimage.label(mask, structure=EIGHT_CONNECTED)
    distance, ridge = ridge_of(mask)

    widths = 2 * distance[ridge] - 1
    angles = component_angles(labels, count, ridge)
    rose = rose_of(angles)
    return {
        "density_pct": round(density, 3),
        "fractal_dimension": round(fractal, 3),
        "fractal_r2": round(r2, 3),
        "crack_count": int(count),
        "total_length_px": float(ridge.sum()),
        "mean_width_px": round(float(widths.mean()), 2) if widths.size
        else 0.0,
        "max_width_px": round(float(2 * distance.max() - 1), 2)
        if count else 0.0,
        "rose": rose,
        "dominant_angles": dominant_angles(angles, rose),
        "severity": severity_of(density, fractal),
    }
