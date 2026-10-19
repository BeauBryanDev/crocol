import io

import numpy as np
from PIL import Image

OVERLAY_MAX_SIDE = 1024
OVERLAY_ALPHA = 0.6
OVERLAY_QUALITY = 80
PREVIEW_QUALITY = 85
CRACK_RGB = np.array([230, 40, 40], dtype=np.float32)


def webp_bytes(image: Image.Image, lossless: bool = False) -> bytes:

    image.thumbnail((OVERLAY_MAX_SIDE, OVERLAY_MAX_SIDE))
    buffer = io.BytesIO()
    if lossless:
        image.save(buffer, format="WEBP", lossless=True, method=4)
    else:
        image.save(buffer, format="WEBP", quality=OVERLAY_QUALITY, method=4)
    return buffer.getvalue()


def overlay_webp(rgb: np.ndarray, mask: np.ndarray) -> bytes:
    """Cracks painted red over the photo, as a compact WebP."""
    blended = rgb.astype(np.float32)
    blended[mask] = ((1 - OVERLAY_ALPHA) * blended[mask]
                     + OVERLAY_ALPHA * CRACK_RGB)
    image = Image.fromarray(blended.clip(0, 255).astype(np.uint8))
    return webp_bytes(image)


def mask_webp(mask: np.ndarray) -> bytes:
    """Cracks alone on a transparent canvas, same size as the overlay."""
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[mask, :3] = CRACK_RGB.astype(np.uint8)
    rgba[mask, 3] = 255
    return webp_bytes(Image.fromarray(rgba, mode="RGBA"), lossless=True)


def preview_jpeg(rgb: np.ndarray) -> bytes:
    """The validated, downscaled photo for a multimodal model."""
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="JPEG", quality=PREVIEW_QUALITY)
    return buffer.getvalue()
