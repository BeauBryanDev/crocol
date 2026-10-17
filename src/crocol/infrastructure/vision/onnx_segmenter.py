import io
import json
import time
from functools import cached_property
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps
from scipy import ndimage

from config.exceptions import (
    ImageTooLargeError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from config.settings import (
    VISION_BATCH,
    VISION_BORDER_PX,
    VISION_CONFIG,
    VISION_FORMATS,
    VISION_LABEL,
    VISION_MAX_BYTES,
    VISION_MAX_PIXELS,
    VISION_MAX_SIDE,
    VISION_MIN_COMPONENT_PX,
    VISION_MODEL,
    VISION_THREADS,
    VISION_THRESHOLD,
)
from crocol.domains.models.cracks import CrackAnalysis, CrackReport
from crocol.infrastructure.vision.crack_metrics import EIGHT_CONNECTED, measure

AMBIGUITY_BAND = 0.1
OVERLAY_MAX_SIDE = 1024
OVERLAY_ALPHA = 0.6
OVERLAY_QUALITY = 80
PREVIEW_QUALITY = 85
CRACK_RGB = np.array([230, 40, 40], dtype=np.float32)


def decode(image_bytes: bytes) -> np.ndarray:
    """Validated RGB image (HxWx3 uint8), EXIF-oriented and downscaled."""
    if len(image_bytes) > VISION_MAX_BYTES:
        raise ImageTooLargeError()
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise InvalidImageError() from exc
    if image.format not in VISION_FORMATS:
        raise UnsupportedImageFormatError()
    if image.width * image.height > VISION_MAX_PIXELS:
        raise ImageTooLargeError()

    try:
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise InvalidImageError() from exc
    image.thumbnail((VISION_MAX_SIDE, VISION_MAX_SIDE),
                    Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.uint8)


def tile_starts(length: int, tile: int, stride: int) -> list[int]:

    if length <= tile:
        return [0]
    starts = list(range(0, length - tile + 1, stride))
    if starts[-1] != length - tile:
        starts.append(length - tile)
    return starts


def clear_border(mask: np.ndarray, pixels: int) -> np.ndarray:
    """Drop a thin frame where the model reacts to the image edge."""
    cleared = mask.copy()
    if pixels > 0:
        cleared[:pixels, :] = cleared[-pixels:, :] = False
        cleared[:, :pixels] = cleared[:, -pixels:] = False
    return cleared


def remove_specks(mask: np.ndarray, min_pixels: int) -> np.ndarray:

    labels, count = ndimage.label(mask, structure=EIGHT_CONNECTED)
    if not count:
        return mask
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_pixels
    keep[0] = False
    return keep[labels]


def overlay_webp(rgb: np.ndarray, mask: np.ndarray) -> bytes:
    """Cracks painted red over the photo, as a compact WebP."""
    blended = rgb.astype(np.float32)
    blended[mask] = ((1 - OVERLAY_ALPHA) * blended[mask]
                     + OVERLAY_ALPHA * CRACK_RGB)
    image = Image.fromarray(blended.clip(0, 255).astype(np.uint8))
    image.thumbnail((OVERLAY_MAX_SIDE, OVERLAY_MAX_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=OVERLAY_QUALITY, method=4)
    return buffer.getvalue()


def preview_jpeg(rgb: np.ndarray) -> bytes:
    """The validated, downscaled photo for a multimodal model."""
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="JPEG", quality=PREVIEW_QUALITY)
    return buffer.getvalue()


def sanitize(image_bytes: bytes) -> bytes:
    """Validated, downscaled JPEG with no EXIF (no GPS or camera data)."""
    return preview_jpeg(decode(image_bytes))


class OnnxCrackAnalyzer:
    """MobileNetV2-UNet crack segmentation with SAHI-style tiling on CPU."""

    def __init__(self,
                 model_path: Path = VISION_MODEL,
                 config_path: Path = VISION_CONFIG,
                 threshold: float = VISION_THRESHOLD
                 ) -> None:

        config = json.loads(config_path.read_text(encoding="utf-8"))
        self._model_path = model_path
        self._threshold = threshold
        self._tile = int(config["img_size"])
        overlap = float(config["preprocessing"]["sahi_overlap_ratio"])
        self._stride = max(1, int(self._tile * (1 - overlap)))
        self._mean = np.array(config["mean"], dtype=np.float32)
        self._std = np.array(config["std"], dtype=np.float32)
        self._input = config["onnx"]["input"]
        self._version = config.get("model_version", "")

    @cached_property
    def session(self) -> ort.InferenceSession:

        options = ort.SessionOptions()
        options.intra_op_num_threads = VISION_THREADS
        options.inter_op_num_threads = 1
        return ort.InferenceSession(str(self._model_path), options,
                                    providers=["CPUExecutionProvider"])

    def normalize(self, rgb: np.ndarray) -> np.ndarray:

        scaled = rgb.astype(np.float32) / 255.0
        return ((scaled - self._mean) / self._std).transpose(2, 0, 1)

    def run_tiles(self, image: np.ndarray) -> tuple[np.ndarray, int]:
        """Per-pixel crack probability, averaging overlapping tiles."""
        tile = self._tile
        height, width = image.shape[:2]
        pad_h, pad_w = max(0, tile - height), max(0, tile - width)
        padded = np.pad(image, ((0, pad_h), (0, pad_w), (0, 0)),
                        mode="reflect")
        rows = tile_starts(padded.shape[0], tile, self._stride)
        cols = tile_starts(padded.shape[1], tile, self._stride)
        boxes = [(r, c) for r in rows for c in cols]

        logits = np.zeros(padded.shape[:2], dtype=np.float32)
        counts = np.zeros(padded.shape[:2], dtype=np.float32)
        for start in range(0, len(boxes), VISION_BATCH):
            batch = boxes[start:start + VISION_BATCH]
            tensor = np.stack([self.normalize(
                padded[r:r + tile, c:c + tile]) for r, c in batch])
            output = self.session.run(None, {self._input: tensor})[0]
            for (r, c), tile_logits in zip(batch, output[:, 0]):
                logits[r:r + tile, c:c + tile] += tile_logits
                counts[r:r + tile, c:c + tile] += 1

        averaged = logits / np.maximum(counts, 1)
        probability = 1.0 / (1.0 + np.exp(-averaged))
        return probability[:height, :width], len(boxes)

    def analyze(self, image_bytes: bytes) -> CrackAnalysis:

        started = time.perf_counter()
        rgb = decode(image_bytes)
        probability, tiles = self.run_tiles(rgb)
        raw = clear_border(probability >= self._threshold, VISION_BORDER_PX)
        mask = remove_specks(raw, VISION_MIN_COMPONENT_PX)

        crack_pixels = probability[mask]
        near = np.abs(crack_pixels - self._threshold) < AMBIGUITY_BAND
        metrics = measure(mask)
        report = CrackReport(
            model=f"{VISION_LABEL} v{self._version}".strip(),
            threshold=self._threshold,
            width_px=int(rgb.shape[1]),
            height_px=int(rgb.shape[0]),
            tiles=tiles,
            density_pct=metrics["density_pct"],
            fractal_dimension=metrics["fractal_dimension"],
            fractal_r2=metrics["fractal_r2"],
            crack_count=metrics["crack_count"],
            total_length_px=metrics["total_length_px"],
            mean_width_px=metrics["mean_width_px"],
            max_width_px=metrics["max_width_px"],
            severity=metrics["severity"],
            mean_confidence=round(float(crack_pixels.mean()), 3)
            if crack_pixels.size else 0.0,
            ambiguous_pct=round(float(near.mean() * 100), 1)
            if crack_pixels.size else 0.0,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            dominant_angles=tuple(metrics["dominant_angles"]),
            rose=tuple(metrics["rose"]),
        )
        return CrackAnalysis(report=report,
                             overlay_webp=overlay_webp(rgb, mask),
                             preview_jpeg=preview_jpeg(rgb))
