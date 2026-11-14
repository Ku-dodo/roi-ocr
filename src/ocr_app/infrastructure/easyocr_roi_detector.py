from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

from ocr_app.domain.models import Roi, next_roi_color


class EasyOcrRoiDetector:
    """문자열 인식 모델 없이 EasyOCR 검출 모델로 글자 영역을 찾는 어댑터."""

    def __init__(self, model_directory: Path, allow_download: bool = False) -> None:
        """CPU용 CRAFT 검출 모델을 준비한다.

        Args:
            model_directory: 검출 모델을 읽거나 다운로드할 폴더.
            allow_download: 모델이 없을 때 다운로드를 허용할지 여부.

        Returns:
            None. 준비한 EasyOCR Reader를 인스턴스에 저장한다.
        """
        import easyocr

        model_directory.mkdir(parents=True, exist_ok=True)
        self._reader = easyocr.Reader(
            ["en"], gpu=False, recognizer=False,
            model_storage_directory=str(model_directory),
            download_enabled=allow_download, verbose=False,
        )

    def detect(self, image: Any, existing: Sequence[Roi] = ()) -> tuple[Roi, ...]:
        """이미지의 글자 위치를 검출하고 검토 가능한 ROI 후보로 변환한다.

        Args:
            image: 원본 크기의 OpenCV 이미지 배열. shape에서 높이와 너비를 읽는다.
            existing: 유지할 기존 ROI. 포함 관계, Tag 중복, 사용 색상 판단에 사용한다.

        Returns:
            원본 픽셀 좌표의 ROI 튜플. 면적 내림차순이며 완전히 포함된 후보는
            제외한다. 후보가 없으면 빈 튜플을 반환하고 기존 ROI는 변경하지 않는다.
        """
        horizontal, free = self._reader.detect(
            image, min_size=8, add_margin=0.08, width_ths=0.5,
        )
        boxes = []
        for page in horizontal:
            for left, right, top, bottom in page:
                boxes.append((left, top, right, bottom))
        for page in free:
            for polygon in page:
                xs, ys = zip(*polygon)
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
        height, width = image.shape[:2]
        return make_roi_candidates(boxes, width, height, existing)


def make_roi_candidates(
    boxes: Sequence[Sequence[float]], width: int, height: int,
    existing: Sequence[Roi] = (),
) -> tuple[Roi, ...]:
    """검출 박스를 이미지 경계로 제한하고 포함 관계·Tag·색상을 정리한다.

    Args:
        boxes: 원본 픽셀 좌표의 (left, top, right, bottom) 박스 목록.
        width: 원본 이미지의 너비.
        height: 원본 이미지의 높이.
        existing: 보존할 기존 ROI 목록. 좌표, Tag, 색상을 변경하지 않는다.

    Returns:
        면적 내림차순의 ROI 후보 튜플. 유효하지 않거나 너무 작은 박스,
        중복 박스, 기존 ROI 또는 앞서 채택한 후보에 완전히 포함된 박스는
        제외한다. 일부만 겹치는 박스는 유지하며 새 Tag와 팔레트 색상을 배정한다.
    """
    bounds = []
    for left, top, right, bottom in boxes:
        if not all(math.isfinite(value) for value in (left, top, right, bottom)):
            continue
        x = max(0, min(width, math.floor(left)))
        y = max(0, min(height, math.floor(top)))
        right = max(0, min(width, math.ceil(right)))
        bottom = max(0, min(height, math.ceil(bottom)))
        if right - x >= 4 and bottom - y >= 4:
            bounds.append((x, y, right - x, bottom - y))
    candidates = []
    used_tags = {roi.tag for roi in existing}
    number = 1
    for x, y, w, h in sorted(set(bounds), key=lambda box: (-box[2] * box[3], box[1], box[0], box[2], box[3])):
        occupied = (*existing, *candidates)
        if any(other.x <= x and other.y <= y
               and x + w <= other.x + other.width
               and y + h <= other.y + other.height for other in occupied):
            continue
        while f"ui_{number}" in used_tags:
            number += 1
        tag = f"ui_{number}"
        used_tags.add(tag)
        candidates.append(Roi(x, y, w, h, tag, next_roi_color(occupied)))
    return tuple(candidates)
