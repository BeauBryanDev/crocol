import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from config.settings import VISION_MAX_SIDE, VISION_MODEL
from crocol.infrastructure.vision.onnx_segmenter import (
    OnnxCrackAnalyzer,
    clear_border,
    decode,
    remove_specks,
    tile_starts,
)

SAMPLES = Path(__file__).resolve().parents[1] / "images2test"


def encoded(width: int, height: int, fmt: str = "JPEG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (120, 110, 100)).save(buffer,
                                                             format=fmt)
    return buffer.getvalue()


def test_decode_downscales_large_photos() -> None:
    rgb = decode(encoded(3000, 1500))
    assert rgb.shape == (VISION_MAX_SIDE // 2, VISION_MAX_SIDE, 3)
    assert rgb.dtype == np.uint8


@pytest.mark.parametrize(
    "payload",
    [b"not an image at all", encoded(64, 64, "GIF"), encoded(64, 64, "BMP")],
)
def test_decode_rejects_bad_or_unsupported_input(payload: bytes) -> None:
    with pytest.raises(ValueError):
        decode(payload)


def test_decode_rejects_oversized_files() -> None:
    with pytest.raises(ValueError):
        decode(b"\xff" * (11 * 1024 * 1024))


def test_tiles_cover_the_whole_axis() -> None:
    assert tile_starts(200, 224, 179) == [0]
    starts = tile_starts(600, 224, 179)
    assert starts[0] == 0 and starts[-1] == 600 - 224
    assert all(b - a <= 179 for a, b in zip(starts, starts[1:]))


def test_cleanup_drops_specks_and_the_border_frame() -> None:
    mask = np.zeros((100, 100), dtype=bool)
    mask[50, 10:90] = True
    mask[5:7, 5:7] = True
    mask[:, 0] = True
    cleaned = remove_specks(clear_border(mask, 3), 30)
    assert cleaned[50, 10:90].all()
    assert not cleaned[5:7, 5:7].any()
    assert not cleaned[:, 0].any()


@pytest.mark.skipif(not VISION_MODEL.exists(), reason="model file missing")
def test_real_photo_end_to_end() -> None:
    photos = sorted(SAMPLES.glob("sunday_crack_04.*"))
    if not photos:
        pytest.skip("images2test/ sample not available")
    analysis = OnnxCrackAnalyzer().analyze(photos[0].read_bytes())
    report = analysis.report
    assert report.model == "MobileNetV2-UNet v2.0.0"
    assert report.threshold == 0.5
    assert report.crack_count >= 1
    assert 1.0 <= report.fractal_dimension <= 2.0
    assert report.severity in {"low", "moderate", "high", "critical"}
    assert analysis.overlay_webp[:4] == b"RIFF"
    assert len(analysis.overlay_webp) < 200 * 1024
