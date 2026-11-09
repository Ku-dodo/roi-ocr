from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ocr_app.domain.models import Roi
from ocr_app.infrastructure.opencv_processor import OpenCvImageProcessor


class ArrayImageLoader:
    def __init__(self, image: np.ndarray) -> None:
        self.image = image

    def load(self, path: Path) -> np.ndarray:
        return self.image


class OpenCvImageProcessorTests(unittest.TestCase):
    def test_one_x_returns_cropped_image_without_scaling(self) -> None:
        image = np.arange(4 * 5 * 3, dtype=np.uint8).reshape((4, 5, 3))
        processor = OpenCvImageProcessor(ArrayImageLoader(image))

        processed = processor.process(Path("unused.png"), Roi(1, 1, 2, 2), 1)

        np.testing.assert_array_equal(image[1:3, 1:3], processed)

    def test_crops_then_scales_with_nearest_neighbor(self) -> None:
        image = np.arange(4 * 5 * 3, dtype=np.uint8).reshape((4, 5, 3))
        processor = OpenCvImageProcessor(ArrayImageLoader(image))

        processed = processor.process(Path("unused.png"), Roi(1, 1, 2, 2), 2)

        self.assertEqual((4, 4, 3), processed.shape)
        np.testing.assert_array_equal(image[1, 1], processed[0, 0])
        np.testing.assert_array_equal(image[1, 1], processed[1, 1])
        np.testing.assert_array_equal(image[2, 2], processed[3, 3])

    def test_roi_is_clamped_to_image_bounds(self) -> None:
        image = np.zeros((4, 5, 3), dtype=np.uint8)
        cropped = OpenCvImageProcessor._crop(image, Roi(3, 2, 10, 10))
        self.assertEqual((2, 2, 3), cropped.shape)

    def test_screenshot_preprocessing_removes_color_and_binarizes(self) -> None:
        image = np.zeros((4, 5, 3), dtype=np.uint8)
        image[1:3, 1:4] = (150, 220, 255)
        processor = OpenCvImageProcessor(
            ArrayImageLoader(image),
            screenshot_preprocessing=True,
        )

        processed = processor.process(Path("unused.png"), None, 2)

        self.assertEqual((8, 10), processed.shape)
        self.assertTrue(set(np.unique(processed)).issubset({0, 255}))


if __name__ == "__main__":
    unittest.main()
