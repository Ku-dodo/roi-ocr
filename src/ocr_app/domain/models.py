from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Sequence


SUPPORTED_SCALE_FACTORS = (1, 2, 4)
REVIEW_CONFIDENCE_THRESHOLD = 0.8
ROI_COLORS = ("#45a3ff", "#ffb347", "#72d98b", "#d58bff", "#ff7272", "#55d6d0", "#ff82be", "#c7d94a")


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


def next_roi_color(rois: Sequence[Roi]) -> str:
    """기존 ROI에서 사용하지 않은 팔레트 색상을 우선 선택한다.

    Args:
        rois: 색상이 이미 배정된 ROI 목록. 색상 비교 시 대소문자를 무시한다.

    Returns:
        #RRGGBB 형식의 색상 문자열. 모든 팔레트 색상을 사용했다면
        기존 ROI 개수를 기준으로 팔레트를 순환한다.
    """
    used_colors = {roi.color.lower() for roi in rois}
    return next((color for color in ROI_COLORS if color not in used_colors),
                ROI_COLORS[len(rois) % len(ROI_COLORS)])


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
    roi_preset_name: str | None = None
    roi_preset_snapshot: tuple[Roi, ...] = ()
    roi_override: bool = False

    @property
    def has_custom_rois(self) -> bool:
        """입력 인자 없이 이 이미지가 기본 ROI와 별도의 영역을 사용하는지 확인한다.

        Returns:
            파일별 프리셋 또는 자동 찾기 초안이 지정돼 있으면 True,
            공통 기본 ROI를 따르는 이미지이면 False.
        """
        return self.roi_override or self.roi_preset_name is not None

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
        """저장된 처리 결과에서 CSV용 검토 상태를 계산한다. 입력 인자는 없다.

        Returns:
            처리 오류면 Fail, 빈 문자열·누락/비정상/기준 미달 신뢰도면 Need Review,
            나머지는 Done. Done은 원문 대조를 마쳤다는 뜻이 아니다.
        """
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
