from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence

from ocr_app.domain.models import Roi


class EasyOcrRoiDetector:
    """Detect text positions without loading a recognition model."""

    def __init__(self, model_directory: Path, allow_download: bool = False) -> None:
        import easyocr

        model_directory.mkdir(parents=True, exist_ok=True)
        self._reader = easyocr.Reader(
            ["en"], gpu=False, recognizer=False,
            model_storage_directory=str(model_directory),
            download_enabled=allow_download, verbose=False,
        )

    def detect(self, image: Any, existing: Sequence[Roi] = ()) -> tuple[Roi, ...]:
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
    """Clamp to original pixels and omit boxes already covered by a manual ROI."""
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
    for x, y, w, h in sorted(set(bounds), key=lambda box: (box[1], box[0])):
        duplicate = False
        for other in (*existing, *candidates):
            overlap = max(0, min(x + w, other.x + other.width) - max(x, other.x)) * max(
                0, min(y + h, other.y + other.height) - max(y, other.y)
            )
            if overlap / (w * h) >= 0.85:
                duplicate = True
                break
        if duplicate:
            continue
        while f"ui_{number}" in used_tags:
            number += 1
        tag = f"ui_{number}"
        used_tags.add(tag)
        candidates.append(Roi(x, y, w, h, tag, "#ffb347"))
    return tuple(candidates)
