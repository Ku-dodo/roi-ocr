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
        import cv2

        validate_scale_factor(scale_factor)
        image = self._image_loader.load(path)
        cropped = self._crop(image, roi)
        if self._screenshot_preprocessing:
            return self._preprocess_screenshot(cropped, scale_factor)
        if scale_factor == 1:
            return cropped
        return cv2.resize(
            cropped,
            None,
            fx=scale_factor,
            fy=scale_factor,
            interpolation=cv2.INTER_NEAREST,
        )

    @staticmethod
    def _preprocess_screenshot(image: Any, scale_factor: int) -> Any:
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
        if scale_factor == 1:
            return binary
        return cv2.resize(
            binary,
            None,
            fx=scale_factor,
            fy=scale_factor,
            interpolation=cv2.INTER_NEAREST,
        )

    @staticmethod
    def _crop(image: Any, roi: Roi | None) -> Any:
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
