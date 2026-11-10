from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ocr_app.application.process_images import ProcessImagesUseCase
from ocr_app.domain.models import (
    ImageItem,
    ImageStatus,
    OcrRecognition,
    OcrResult,
    Roi,
    validate_scale_factor,
)
from ocr_app.domain.languages import SUPPORTED_LANGUAGES, get_language, reader_languages
from ocr_app.infrastructure.csv_result_writer import CsvResultWriter


class FakeImageProcessor:
    def process(self, path: Path, roi: Roi | None, scale_factor: int) -> str:
        if path.name.startswith("bad"):
            raise ValueError("broken image")
        return f"{path.name}:{scale_factor}:{roi}"


class FakeOcrEngine:
    def recognize(self, image: str) -> OcrRecognition:
        return OcrRecognition(f"recognized {image}", 0.875)


class CapturingWriter:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.results: list[OcrResult] = []

    def write(self, results) -> Path:
        self.results = list(results)
        return self.output_path


class DomainTests(unittest.TestCase):
    def test_language_catalog_matches_easyocr_172(self) -> None:
        self.assertEqual(86, len(SUPPORTED_LANGUAGES))
        self.assertEqual(86, len({language.code for language in SUPPORTED_LANGUAGES}))
        self.assertEqual("korean_g2.pth", get_language("ko").model_filename)
        self.assertEqual(("ko", "en"), reader_languages("ko"))
        self.assertEqual(("en",), reader_languages("en"))

    def test_preprocessing_scale_is_limited_to_one_two_or_four(self) -> None:
        for valid in (1, 2, 4):
            validate_scale_factor(valid)
            self.assertEqual(valid, ImageItem(Path("sample.png"), scale_factor=valid).scale_factor)

        for invalid in (-2, 0, 3, 5, 6, 8, 100):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_scale_factor(invalid)
            with self.subTest(image_scale=invalid), self.assertRaises(ValueError):
                ImageItem(Path("sample.png"), scale_factor=invalid)

    def test_roi_requires_positive_size(self) -> None:
        with self.assertRaises(ValueError):
            Roi(0, 0, 0, 10)


class UseCaseTests(unittest.TestCase):
    def test_batch_continues_after_a_file_failure(self) -> None:
        writer = CapturingWriter(Path("result.csv"))
        use_case = ProcessImagesUseCase(FakeImageProcessor(), FakeOcrEngine(), writer)
        items = [ImageItem(Path("good.png")), ImageItem(Path("bad.png"))]

        summary = use_case.execute(items)

        self.assertEqual(1, summary.succeeded)
        self.assertEqual(1, summary.failed)
        self.assertEqual(ImageStatus.COMPLETED, items[0].status)
        self.assertEqual(ImageStatus.FAILED, items[1].status)
        self.assertEqual(0.875, writer.results[0].confidence)
        self.assertEqual("", writer.results[1].extracted_text)
        self.assertIsNone(writer.results[1].confidence)


class CsvWriterTests(unittest.TestCase):
    def test_file_extension_setting_only_changes_exported_names(self) -> None:
        results = [
            OcrResult("한글.png", "인식 결과", 0.9),
            OcrResult("sample.v2.PNG", "점 포함", None),
            OcrResult("extensionless", "확장자 없음", None),
        ]
        with tempfile.TemporaryDirectory() as temporary_directory:
            for include in (True, False):
                with self.subTest(include_file_extension=include):
                    path = CsvResultWriter(
                        Path(temporary_directory), include_file_extension=include,
                    ).write(results)
                    with path.open(encoding="utf-8-sig", newline="") as stream:
                        rows = list(csv.reader(stream))
                    expected = (
                        ["한글.png", "sample.v2.PNG", "extensionless"]
                        if include else ["한글", "sample.v2", "extensionless"]
                    )
                    self.assertEqual(expected, [row[0] for row in rows[1:]])
                    self.assertEqual(["인식 결과", "90.00%"], rows[1][1:])
                    self.assertEqual("한글.png", results[0].file_name)

    def test_csv_has_required_headers_and_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            output_path = CsvResultWriter(output_directory).write(
                [
                    OcrResult("한글.png", "추출 문자열", 0.93456),
                    OcrResult("빈칸.png", "", None),
                ]
            )

            raw = output_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            with output_path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(
                ["파일 이름", "추출 문자열", "정확도(신뢰도)"], rows[0]
            )
            self.assertEqual(["한글.png", "추출 문자열", "93.46%"], rows[1])
            self.assertEqual(["빈칸.png", "", ""], rows[2])


if __name__ == "__main__":
    unittest.main()
