from __future__ import annotations

from pathlib import Path
from typing import Any


class OpenCvImageLoader:
    def load(self, path: Path) -> Any:
        """한글 등 유니코드 파일 경로에서도 이미지를 바이너리로 읽어 디코딩한다.

        Args:
            path: 읽을 로컬 이미지 경로.

        Returns:
            OpenCV BGR 이미지 배열. 파일이 없으면 FileNotFoundError,
            디코딩할 수 없으면 ValueError를 발생시킨다.
        """
        import cv2
        import numpy as np

        if not path.is_file():
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {path}")

        encoded = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"지원하지 않거나 손상된 이미지입니다: {path.name}")
        return image
