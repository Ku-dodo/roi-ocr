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
        """이미지 처리기·OCR 엔진·저장기를 연결한다.

        Args:
            image_processor: 영역 자르기와 전처리를 담당하는 구현체.
            ocr_engine: 공통 OCR 엔진. 파일별 선택기가 있으면 None이어도 된다.
            result_writer: 전체 영역의 결과를 저장하는 구현체.
            engine_for_item: 이미지마다 엔진을 선택하는 함수. 공통 엔진보다 우선한다.
            default_language_code: 개별 언어를 지정하지 않은 이미지의 결과 언어 코드.

        Returns:
            None. 엔진과 선택기가 모두 없으면 ValueError를 발생시킨다.
        """
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
        """이미지별 ROI를 순차 처리하고 모든 결과를 한 파일에 저장한다.

        Args:
            items: 처리할 이미지 목록. 항목의 상태·결과·오류를 직접 갱신한다.
                ROI가 없으면 전체 이미지를 하나의 영역으로 처리한다.
            progress_callback: (완료 영역 수, 전체 영역 수, 현재 이미지)를 받는 함수.
                처리 시작·영역 완료·이미지 집계 시 호출되므로 횟수는 영역 수보다 많다.

        Returns:
            저장 경로와 이미지 단위 성공·실패 집계. 영역별 오류는 기록하고 계속하며,
            입력 검증 오류와 최종 저장 오류는 호출자에게 전파한다.
        """
        if not items:
            raise ValueError("처리할 이미지가 없습니다.")
        for item in items:
            tags = [roi.tag for roi in item.rois]
            if any(not tag.strip() for tag in tags) or len(tags) != len(set(tags)):
                raise ValueError("ROI Tag / UI ID는 비어 있거나 중복될 수 없습니다.")

        results: list[OcrResult] = []
        succeeded = 0
        failed = 0
        total = sum(max(1, len(item.rois)) for item in items)
        completed = 0

        for item in items:
            item.status = ImageStatus.PROCESSING
            item.error_message = ""
            item.extracted_text = ""
            item.confidence = None
            item.results.clear()
            item.active_roi_id = None
            if progress_callback is not None:
                progress_callback(completed, total, item)

            errors: list[str] = []
            for roi in item.rois or (None,):
                ui_id = roi.tag if roi is not None else "full_image"
                item.active_roi_id = ui_id
                if progress_callback is not None:
                    progress_callback(completed, total, item)
                try:
                    processed_image = self._image_processor.process(item.path, roi, item.scale_factor)
                    engine = self._engine_for_item(item) if self._engine_for_item else self._ocr_engine
                    assert engine is not None
                    recognition = engine.recognize(processed_image)
                    result = OcrResult(
                        ui_id=ui_id,
                        extracted_text=recognition.text,
                        confidence=recognition.confidence,
                        language_code=item.language_code or self._default_language_code,
                    )
                except Exception as error:  # Continue with the other regions and files.
                    errors.append(f"{ui_id}: {error}")
                    result = OcrResult(
                        ui_id=ui_id,
                        extracted_text="",
                        language_code=item.language_code or self._default_language_code,
                        processing_failed=True,
                        error_message=str(error),
                    )
                item.results.append(result)
                item.active_roi_id = None
                completed += 1
                if progress_callback is not None:
                    progress_callback(completed, total, item)
            results.extend(item.results)
            item.error_message = "\n".join(errors)
            item.extracted_text = "\n".join(
                f"[{r.ui_id}] {r.extracted_text}" for r in item.results if not r.processing_failed
            )
            confidences = [r.confidence for r in item.results if r.confidence is not None]
            item.confidence = sum(confidences) / len(confidences) if confidences else None
            item.status = ImageStatus.FAILED if errors else ImageStatus.COMPLETED
            if errors:
                failed += 1
            else:
                succeeded += 1
            if progress_callback is not None:
                progress_callback(completed, total, item)

        output_path = self._result_writer.write(results)
        return BatchProcessingSummary(output_path, succeeded, failed)
