from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ROI의 너비와 높이는 0보다 커야 합니다.")


@dataclass(slots=True)
class ImageItem:
    path: Path
    roi: Roi | None = None
    scale_factor: int = 1
    extracted_text: str = ""
    confidence: float | None = None
    status: ImageStatus = ImageStatus.READY
    error_message: str = ""

    def __post_init__(self) -> None:
        self.path = self.path.resolve()
        validate_scale_factor(self.scale_factor)


@dataclass(frozen=True, slots=True)
class OcrRecognition:
    text: str
    confidence: float | None


@dataclass(frozen=True, slots=True)
class OcrResult:
    file_name: str
    extracted_text: str
    confidence: float | None = None


def validate_scale_factor(scale_factor: int) -> None:
    if scale_factor != 1 and (scale_factor <= 0 or scale_factor % 2 != 0):
        raise ValueError("확대 배율은 1 또는 양의 짝수여야 합니다.")
