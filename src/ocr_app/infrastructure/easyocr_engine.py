from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

from ocr_app.domain.models import OcrRecognition


class EasyOcrEngine:
    def __init__(
        self,
        model_directory: Path,
        languages: Sequence[str] = ("ko", "en"),
        use_gpu: bool = False,
        allow_download: bool = False,
    ) -> None:
        import easyocr

        model_directory.mkdir(parents=True, exist_ok=True)
        self._reader = easyocr.Reader(
            list(languages),
            gpu=use_gpu,
            model_storage_directory=str(model_directory),
            download_enabled=allow_download,
            verbose=False,
        )

    def recognize(self, image: Any) -> OcrRecognition:
        detected = self._reader.readtext(
            image,
            detail=1,
            paragraph=False,
            contrast_ths=0.05,
            adjust_contrast=0.7,
            add_margin=0.2,
        )

        texts: list[str] = []
        confidences: list[float] = []
        for detection in detected:
            if not isinstance(detection, (list, tuple)) or len(detection) < 2:
                continue

            text = " ".join(str(detection[1]).split())
            if not text:
                continue
            texts.append(text)

            if len(detection) < 3:
                continue
            try:
                confidence = float(detection[2])
            except (TypeError, ValueError):
                continue
            if math.isfinite(confidence):
                confidences.append(min(1.0, max(0.0, confidence)))

        average_confidence = (
            sum(confidences) / len(confidences) if confidences else None
        )
        return OcrRecognition(" ".join(texts), average_confidence)
