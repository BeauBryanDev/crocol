import io

import numpy as np
import pytest
from PIL import Image
from test_api_routes import FakeAsk, client_for, make_state

from crocol.infrastructure.vision.renders import (
    OVERLAY_MAX_SIDE,
    mask_webp,
    overlay_webp,
)


def decoded(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def test_mask_is_transparent_except_on_cracks() -> None:
    mask = np.zeros((60, 80), dtype=bool)
    mask[30, 10:70] = True
    mask[5:50, 40] = True

    image = decoded(mask_webp(mask))
    alpha = np.asarray(image.convert("RGBA"))[:, :, 3]
    assert image.mode == "RGBA"
    assert np.array_equal(alpha > 0, mask)


def test_mask_and_overlay_share_size_after_thumbnail() -> None:
    mask = np.zeros((900, 2048), dtype=bool)
    mask[450, :] = True
    rgb = np.full((900, 2048, 3), 120, dtype=np.uint8)

    mask_image = decoded(mask_webp(mask))
    overlay_image = decoded(overlay_webp(rgb, mask))
    assert mask_image.size == overlay_image.size
    assert max(mask_image.size) == OVERLAY_MAX_SIDE


VISION = {
    "report": {
        "model": "MobileNetV2-UNet v2.0.0", "threshold": 0.5,
        "width_px": 612, "height_px": 459, "tiles": 12,
        "density_pct": 4.54, "fractal_dimension": 1.417,
        "fractal_r2": 0.998, "crack_count": 3, "total_length_px": 812.0,
        "mean_width_px": 6.0, "max_width_px": 11.0, "severity": "high",
        "mean_confidence": 0.92, "ambiguous_pct": 3.9, "elapsed_ms": 1028,
        "dominant_angles": [[17.0, 0.79]], "rose": [0.0] * 18,
    },
    "mask_webp_b64": "UklGRg==",
    "interpretation": {
        "is_rock": True, "rock_description": "Arenisca gris.",
        "diagnosis": "Fracturamiento alto.", "fluid_flow": "Por fracturas.",
        "confidence": "medium",
    },
}


class VisionAsk(FakeAsk):
    def final(self) -> dict:
        return {**super().final(), "vision": VISION}


@pytest.mark.anyio
async def test_image_answer_passes_the_vision_result_through(
        tmp_path) -> None:
    state = make_state(tmp_path)
    state.ask = VisionAsk()
    async with client_for(state) as client:
        response = await client.post("/api/chat",
                                     json={"question": "describe la roca"})
    body = response.json()
    assert response.status_code == 200
    assert body["vision"]["report"]["severity"] == "high"
    assert body["vision"]["report"]["dominant_angles"] == [[17.0, 0.79]]
    assert body["vision"]["interpretation"]["confidence"] == "medium"
