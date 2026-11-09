from __future__ import annotations

from pathlib import Path
from typing import Any


class OpenCvImageLoader:
    def load(self, path: Path) -> Any:
        import cv2
        import numpy as np

        if not path.is_file():
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {path}")

        encoded = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"지원하지 않거나 손상된 이미지입니다: {path.name}")
        return image
