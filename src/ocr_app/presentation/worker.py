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
    ) -> None:
        super().__init__()
        self._items = list(items)
        self._model_directory = model_directory
        self._result_directory = result_directory
        self._languages = tuple(languages)
        self._screenshot_preprocessing = screenshot_preprocessing
        self._allow_model_download = allow_model_download
        self.signals = OcrWorkerSignals()

    @Slot()
    def run(self) -> None:
        """입력 인자 없이 생성 시 보관한 이미지·설정으로 OCR 파이프라인을 실행한다.

        Returns:
            None. 영역별 진행은 progress, 저장 완료 요약은 finished 신호로 보낸다.
            전체 실행 예외는 failed로 전달하며 개별 영역 오류는 유스케이스가 기록한다.
        """
        try:
            # Keep only the current reader: many language models can exhaust RAM.
            active_languages = None
            active_engine = None

            def engine_for_item(item: ImageItem) -> EasyOcrEngine:
                """개별 언어 또는 기본 언어에 맞는 엔진 하나만 메모리에 유지한다.

                Args:
                    item: 인식할 이미지. 개별 언어가 없으면 작업의 기본 언어를 쓴다.

                Returns:
                    현재 언어 조합의 EasyOcrEngine. 언어가 바뀌면 이전 엔진을 해제하고
                    다시 로드하므로 여러 언어 모델이 동시에 누적되지 않는다.
                """
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
                result_writer=CsvResultWriter(self._result_directory),
            )
            summary = use_case.execute(self._items, self.signals.progress.emit)
            self.signals.finished.emit(summary)
        except Exception as error:
            self.signals.failed.emit(str(error))
