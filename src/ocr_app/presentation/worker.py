from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ocr_app.application.process_images import ProcessImagesUseCase
from ocr_app.domain.models import ImageItem
from ocr_app.infrastructure.csv_result_writer import CsvResultWriter
from ocr_app.infrastructure.easyocr_engine import EasyOcrEngine
from ocr_app.infrastructure.opencv_processor import OpenCvImageProcessor


class OcrWorkerSignals(QObject):
    progress = Signal(int, int, object)
    finished = Signal(object)
    failed = Signal(str)


class OcrWorker(QRunnable):
    def __init__(
        self,
        items: Sequence[ImageItem],
        model_directory: Path,
        result_directory: Path,
        languages: Sequence[str],
        screenshot_preprocessing: bool = False,
        allow_model_download: bool = False,
        include_file_extension: bool = True,
    ) -> None:
        super().__init__()
        self._items = list(items)
        self._model_directory = model_directory
        self._result_directory = result_directory
        self._languages = tuple(languages)
        self._screenshot_preprocessing = screenshot_preprocessing
        self._allow_model_download = allow_model_download
        self._include_file_extension = include_file_extension
        self.signals = OcrWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            use_case = ProcessImagesUseCase(
                image_processor=OpenCvImageProcessor(
                    screenshot_preprocessing=self._screenshot_preprocessing
                ),
                ocr_engine=EasyOcrEngine(
                    model_directory=self._model_directory,
                    languages=self._languages,
                    use_gpu=False,
                    allow_download=self._allow_model_download,
                ),
                result_writer=CsvResultWriter(
                    self._result_directory,
                    include_file_extension=self._include_file_extension,
                ),
            )
            summary = use_case.execute(self._items, self.signals.progress.emit)
            self.signals.finished.emit(summary)
        except Exception as error:
            self.signals.failed.emit(str(error))
