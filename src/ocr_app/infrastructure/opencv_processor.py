from __future__ import annotations

from pathlib import Path
from typing import Any

from ocr_app.domain.models import Roi, validate_scale_factor
from ocr_app.infrastructure.image_loader import OpenCvImageLoader


class OpenCvImageProcessor:
    def __init__(
        self,
        image_loader: OpenCvImageLoader | None = None,
        screenshot_preprocessing: bool = False,
    ) -> None:
        self._image_loader = image_loader or OpenCvImageLoader()
        self._screenshot_preprocessing = screenshot_preprocessing

    def process(self, path: Path, roi: Roi | None, scale_factor: int) -> Any:
        """원본에서 ROI를 자른 뒤 선택적 콘솔 전처리와 최근접 이웃 확대를 수행한다.

        Args:
            path: 원본 이미지 파일 경로.
            roi: 원본 픽셀 좌표의 영역. None이면 전체 이미지를 사용한다.
            scale_factor: 허용된 확대 배율(1, 2, 4).

        Returns:
            OCR 입력 배열. 일반 모드는 BGR, 콘솔 전처리 모드는 이진 흑백 이미지이다.
        """
        import cv2

        validate_scale_factor(scale_factor)
        image = self._crop(self._image_loader.load(path), roi)
        if self._screenshot_preprocessing:
            image = self._preprocess_screenshot(image)
        if scale_factor == 1:
            return image
        return cv2.resize(
            image,
            None,
            fx=scale_factor,
            fy=scale_factor,
            interpolation=cv2.INTER_NEAREST,
        )

    @staticmethod
    def _preprocess_screenshot(image: Any) -> Any:
        """밝기에 따라 색 채널을 합치고 Otsu 이진화로 콘솔 글자 대비를 높인다.

        Args:
            image: BGR 또는 이미 흑백인 이미지 배열.

        Returns:
            1채널 이진 이미지. 검은 배경과 흰 배경의 채널 합성 방식을 달리한다.
        """
        import cv2

        if len(image.shape) == 2:
            gray = image
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blue, green, red = cv2.split(image)
            if cv2.mean(gray)[0] < 127:
                gray = cv2.max(cv2.max(blue, green), red)
            else:
                gray = cv2.min(cv2.min(blue, green), red)

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY | cv2.THRESH_OTSU,
        )
        return binary

    @staticmethod
    def _crop(image: Any, roi: Roi | None) -> Any:
        """이미지 경계를 벗어난 ROI를 경계 안으로 제한하여 자른다.

        Args:
            image: 원본 이미지 배열.
            roi: 자를 픽셀 영역. None이면 자르지 않는다.

        Returns:
            원본 또는 잘린 배열 뷰. 경계 안의 유효 면적이 없으면 ValueError.
        """
        if roi is None:
            return image

        image_height, image_width = image.shape[:2]
        left = max(0, min(roi.x, image_width))
        top = max(0, min(roi.y, image_height))
        right = max(left, min(roi.x + roi.width, image_width))
        bottom = max(top, min(roi.y + roi.height, image_height))

        if right <= left or bottom <= top:
            raise ValueError("ROI가 이미지 범위를 벗어났습니다.")
        return image[top:bottom, left:right]
