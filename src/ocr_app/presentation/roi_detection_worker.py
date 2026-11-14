from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ocr_app.domain.models import Roi
from ocr_app.infrastructure.easyocr_roi_detector import EasyOcrRoiDetector
from ocr_app.infrastructure.image_loader import OpenCvImageLoader


class RoiDetectionSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class RoiDetectionWorker(QRunnable):
    def __init__(self, path: Path, models: Path, existing: tuple[Roi, ...], allow_download: bool):
        super().__init__()
        self.signals = RoiDetectionSignals()
        self._path, self._models = path, models
        self._existing, self._allow_download = existing, allow_download

    @Slot()
    def run(self) -> None:
        try:
            image = OpenCvImageLoader().load(self._path)
            detector = EasyOcrRoiDetector(self._models, self._allow_download)
            self.signals.finished.emit(detector.detect(image, self._existing))
        except Exception as error:
            self.signals.failed.emit(str(error))
