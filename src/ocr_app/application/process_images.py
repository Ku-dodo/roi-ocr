from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from ocr_app.application.ports import ImageProcessor, OcrEngine, ResultWriter
from ocr_app.domain.models import ImageItem, ImageStatus, OcrResult


ProgressCallback = Callable[[int, int, ImageItem], None]


@dataclass(frozen=True, slots=True)
class BatchProcessingSummary:
    output_path: Path
    succeeded: int
    failed: int


class ProcessImagesUseCase:
    def __init__(
        self,
        image_processor: ImageProcessor,
        ocr_engine: OcrEngine | None,
        result_writer: ResultWriter,
        engine_for_item: Callable[[ImageItem], OcrEngine] | None = None,
        default_language_code: str = "ko",
    ) -> None:
        if ocr_engine is None and engine_for_item is None:
            raise ValueError("OCR 엔진 또는 파일별 엔진 선택기가 필요합니다.")
        self._image_processor = image_processor
        self._ocr_engine = ocr_engine
        self._result_writer = result_writer
        self._engine_for_item = engine_for_item
        self._default_language_code = default_language_code

    def execute(
        self,
        items: Sequence[ImageItem],
        progress_callback: ProgressCallback | None = None,
    ) -> BatchProcessingSummary:
        if not items:
            raise ValueError("처리할 이미지가 없습니다.")

        results: list[OcrResult] = []
        succeeded = 0
        failed = 0
        total = len(items)

        for index, item in enumerate(items, start=1):
            item.status = ImageStatus.PROCESSING
            item.error_message = ""
            if progress_callback is not None:
                progress_callback(index - 1, total, item)

            try:
                processed_image = self._image_processor.process(
                    item.path,
                    item.roi,
                    item.scale_factor,
                )
                engine = (
                    self._engine_for_item(item)
                    if self._engine_for_item is not None
                    else self._ocr_engine
                )
                assert engine is not None
                recognition = engine.recognize(processed_image)
                item.extracted_text = recognition.text
                item.confidence = recognition.confidence
                item.status = ImageStatus.COMPLETED
                succeeded += 1
            except Exception as error:  # A failed file must not stop the batch.
                item.extracted_text = ""
                item.confidence = None
                item.status = ImageStatus.FAILED
                item.error_message = str(error)
                failed += 1

            results.append(
                OcrResult(
                    file_name=item.path.name,
                    extracted_text=item.extracted_text,
                    confidence=item.confidence,
                    language_code=item.language_code or self._default_language_code,
                    processing_failed=item.status == ImageStatus.FAILED,
                )
            )
            if progress_callback is not None:
                progress_callback(index, total, item)

        output_path = self._result_writer.write(results)
        return BatchProcessingSummary(output_path, succeeded, failed)
