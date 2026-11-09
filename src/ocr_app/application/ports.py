from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Sequence

from ocr_app.domain.models import OcrRecognition, OcrResult, Roi


class ImageProcessor(Protocol):
    def process(self, path: Path, roi: Roi | None, scale_factor: int) -> Any:
        """Load, crop, and scale an image for OCR."""


class OcrEngine(Protocol):
    def recognize(self, image: Any) -> OcrRecognition:
        """Return normalized text and its average confidence."""


class ResultWriter(Protocol):
    def write(self, results: Sequence[OcrResult]) -> Path:
        """Persist OCR results and return the output path."""
