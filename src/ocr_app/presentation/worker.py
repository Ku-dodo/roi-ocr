from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ocr_app.application.process_images import ProcessImagesUseCase
from ocr_app.domain.models import ImageItem
from ocr_app.domain.languages import reader_languages
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
            # Keep only the current reader: many language models can exhaust RAM.
            active_languages = None
            active_engine = None

            def engine_for_item(item: ImageItem) -> EasyOcrEngine:
                nonlocal active_languages, active_engine
                languages = (
                    reader_languages(item.language_code)
                    if item.language_code is not None
                    else self._languages
                )
                if active_engine is None or languages != active_languages:
                    active_engine = None
                    active_languages = None
                    active_engine = EasyOcrEngine(
                        model_directory=self._model_directory,
                        languages=languages,
                        use_gpu=False,
                        allow_download=self._allow_model_download,
                    )
                    active_languages = languages
                return active_engine

            use_case = ProcessImagesUseCase(
                image_processor=OpenCvImageProcessor(
                    screenshot_preprocessing=self._screenshot_preprocessing
                ),
                ocr_engine=None,
                engine_for_item=engine_for_item,
                default_language_code=self._languages[0],
                result_writer=CsvResultWriter(
                    self._result_directory,
                    include_file_extension=self._include_file_extension,
                ),
            )
            summary = use_case.execute(self._items, self.signals.progress.emit)
            self.signals.finished.emit(summary)
        except Exception as error:
            self.signals.failed.emit(str(error))
