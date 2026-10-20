import math

import numpy as np
import pytest

from crocol.infrastructure.vision.crack_metrics import (
    fractal_dimension,
    measure,
    severity_of,
)

SIZE = 512


def blank() -> np.ndarray:
    return np.zeros((SIZE, SIZE), dtype=bool)


def line(angle_deg: float, thickness: int = 1,
         length: int = 400) -> np.ndarray:
    """A straight line through the centre; angle counterclockwise."""
    mask = blank()
    centre = SIZE / 2
    dx = math.cos(math.radians(angle_deg))
    dy = math.sin(math.radians(angle_deg))
    for t in np.linspace(-length / 2, length / 2, length * 4):
        col = int(round(centre + t * dx))
        row = int(round(centre - t * dy))
        half = thickness // 2
        mask[row - half:row + half + 1, col - half:col + half + 1] = True
    return mask


def test_empty_mask_is_low_and_zero() -> None:
    result = measure(blank())
    assert result["crack_count"] == 0
    assert result["fractal_dimension"] == 0.0
    assert result["severity"] == "low"
    assert result["dominant_angles"] == []


def test_straight_line_has_dimension_one() -> None:
    dimension, r2 = fractal_dimension(line(0))
    assert dimension == pytest.approx(1.0, abs=0.05)
    assert r2 > 0.99


def test_filled_square_has_dimension_two() -> None:
    mask = blank()
    mask[:, :] = True
    assert fractal_dimension(mask)[0] == pytest.approx(2.0, abs=0.05)


@pytest.mark.parametrize("angle", [0, 30, 45, 90, 135, 160])
def test_orientation_matches_the_drawn_angle(angle: float) -> None:
    dominant = measure(line(angle, thickness=3))["dominant_angles"]
    measured = dominant[0][0]
    difference = abs((measured - angle + 90) % 180 - 90)
    assert difference <= 3


def test_width_and_length_of_a_thick_line() -> None:
    result = measure(line(0, thickness=5, length=300))
    assert result["mean_width_px"] == pytest.approx(5, abs=1)
    assert result["total_length_px"] == pytest.approx(300, rel=0.1)


def test_separate_cracks_are_counted() -> None:
    mask = line(0) | line(90)
    mask[SIZE // 2 - 30:SIZE // 2 + 30, SIZE // 2 - 30:SIZE // 2 + 30] = False
    assert measure(mask)["crack_count"] == 4


def test_two_crack_sets_give_two_dominant_angles() -> None:
    mask = blank()
    for offset in (-150, -50, 50, 150):
        mask |= np.roll(line(20, length=200), offset, axis=0)
        mask |= np.roll(line(110, length=200), offset, axis=1)
    angles = sorted(a for a, _ in measure(mask)["dominant_angles"][:2])
    assert angles[0] == pytest.approx(20, abs=3)
    assert angles[1] == pytest.approx(110, abs=3)


@pytest.mark.parametrize(
    ("density", "fractal", "expected"),
    [
        (0.5, 1.10, "low"),
        (2.0, 1.25, "moderate"),
        (0.5, 1.40, "moderate"),
        (5.0, 1.40, "high"),
        (9.0, 1.60, "critical"),
        (9.0, 1.10, "high"),
    ],
)
def test_severity_levels(density: float, fractal: float,
                         expected: str) -> None:
    assert severity_of(density, fractal) == expected
