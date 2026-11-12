from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path


SUPPORTED_SCALE_FACTORS = (1, 2, 4)
REVIEW_CONFIDENCE_THRESHOLD = 0.8


class OcrResultStatus(str, Enum):
    DONE = "Done"
    FAIL = "Fail"
    NEED_REVIEW = "Need Review"


class ImageStatus(str, Enum):
    READY = "대기"
    PROCESSING = "처리 중"
    COMPLETED = "완료"
    FAILED = "실패"


@dataclass(frozen=True, slots=True)
class Roi:
    x: int
    y: int
    width: int
    height: int
    tag: str = ""
    color: str = "#45a3ff"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI의 너비와 높이는 0보다 커야 합니다.")


@dataclass(slots=True)
class ImageItem:
    path: Path
    rois: tuple[Roi, ...] = ()
    scale_factor: int = 1
    extracted_text: str = ""
    confidence: float | None = None
    status: ImageStatus = ImageStatus.READY
    error_message: str = ""
    language_code: str | None = None
    results: list[OcrResult] = field(default_factory=list)
    active_roi_id: str | None = None

    def __post_init__(self) -> None:
        self.path = self.path.resolve()
        validate_scale_factor(self.scale_factor)


@dataclass(frozen=True, slots=True)
class OcrRecognition:
    text: str
    confidence: float | None


@dataclass(frozen=True, slots=True)
class OcrResult:
    ui_id: str
    extracted_text: str
    confidence: float | None = None
    language_code: str = "ko"
    processing_failed: bool = False
    error_message: str = ""

    @property
    def status(self) -> OcrResultStatus:
        if self.processing_failed:
            return OcrResultStatus.FAIL
        if (
            not self.extracted_text.strip()
            or self.confidence is None
            or not math.isfinite(self.confidence)
            or not REVIEW_CONFIDENCE_THRESHOLD <= self.confidence <= 1.0
        ):
            return OcrResultStatus.NEED_REVIEW
        return OcrResultStatus.DONE


def validate_scale_factor(scale_factor: int) -> None:
    if scale_factor not in SUPPORTED_SCALE_FACTORS:
        raise ValueError("전처리 확대 배율은 1배, 2배, 4배만 사용할 수 있습니다. (최대 4배)")
