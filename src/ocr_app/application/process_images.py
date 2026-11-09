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
        ocr_engine: OcrEngine,
        result_writer: ResultWriter,
    ) -> None:
        self._image_processor = image_processor
        self._ocr_engine = ocr_engine
        self._result_writer = result_writer

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
                recognition = self._ocr_engine.recognize(processed_image)
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
                OcrResult(item.path.name, item.extracted_text, item.confidence)
            )
            if progress_callback is not None:
                progress_callback(index, total, item)

        output_path = self._result_writer.write(results)
        return BatchProcessingSummary(output_path, succeeded, failed)
