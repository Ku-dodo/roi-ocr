from __future__ import annotations

import csv
import importlib.util
import runpy
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
    OcrResultStatus,
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
    def test_result_status_handles_review_boundary_empty_text_and_failure(self) -> None:
        for text, confidence, failed, expected in (
            ("인식 결과", 0.8, False, OcrResultStatus.DONE),
            ("인식 결과", 0.7999, False, OcrResultStatus.NEED_REVIEW),
            ("인식 결과", None, False, OcrResultStatus.NEED_REVIEW),
            ("  \n", 0.99, False, OcrResultStatus.NEED_REVIEW),
            ("", None, False, OcrResultStatus.NEED_REVIEW),
            ("인식 결과", float("nan"), False, OcrResultStatus.NEED_REVIEW),
            ("", None, True, OcrResultStatus.FAIL),
        ):
            with self.subTest(text=text, confidence=confidence, failed=failed):
                result = OcrResult("sample.png", text, confidence, processing_failed=failed)
                self.assertEqual(expected, result.status)

    def test_language_catalog_matches_easyocr_172(self) -> None:
        spec = importlib.util.find_spec("easyocr")
        config = runpy.run_path(str(Path(spec.origin).parent / "config.py"))
        self.assertEqual(set(config["all_lang_list"]), {language.code for language in SUPPORTED_LANGUAGES})
        model_filenames = {model["filename"] for generation in config["recognition_models"].values()
                           for model in generation.values()}
        self.assertTrue(all(language.model_filename in model_filenames for language in SUPPORTED_LANGUAGES))
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
    def test_progress_reports_each_roi_in_progress_and_completed_results(self) -> None:
        item = ImageItem(Path("sample.png"), rois=(Roi(0, 0, 10, 10, "name"), Roi(20, 0, 10, 10, "button")))
        states = []
        use_case = ProcessImagesUseCase(FakeImageProcessor(), FakeOcrEngine(), CapturingWriter(Path("result.csv")))
        use_case.execute([item], lambda completed, total, current: states.append(
            (current.active_roi_id, [r.ui_id for r in current.results])
        ))
        self.assertIn(("name", []), states)
        self.assertIn(("button", ["name"]), states)
        self.assertEqual((None, ["name", "button"]), states[-1])

    def test_invalid_roi_ids_are_rejected_before_export(self) -> None:
        writer = CapturingWriter(Path("result.csv"))
        use_case = ProcessImagesUseCase(FakeImageProcessor(), FakeOcrEngine(), writer)
        for tags in (("",), ("user_name", "user_name")):
            item = ImageItem(Path("sample.png"), rois=tuple(Roi(0, 0, 10, 10, tag) for tag in tags))
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                use_case.execute([item])
        self.assertEqual([], writer.results)

    def test_multiple_regions_keep_successes_after_one_region_fails(self) -> None:
        class Processor:
            def process(self, path, roi, scale):
                if roi.tag == "broken":
                    raise ValueError("ROI outside image")
                return f"{roi.tag}:{path.stem}"

        regions = (Roi(0, 0, 10, 10, "user_name"), Roi(20, 20, 10, 10, "broken"),
                   Roi(40, 40, 10, 10, "password"))
        items = [ImageItem(Path("screen-ko.png"), rois=regions, language_code="ko"),
                 ImageItem(Path("screen-en.png"), rois=regions, language_code="en")]
        with tempfile.TemporaryDirectory() as directory:
            use_case = ProcessImagesUseCase(Processor(), FakeOcrEngine(), CsvResultWriter(Path(directory)))
            summary = use_case.execute(items)
            with summary.output_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
        self.assertEqual(7, len(rows))
        self.assertEqual(["user_name", "broken", "password"] * 2, [r[0] for r in rows[1:]])
        self.assertEqual(["ko"] * 3 + ["en"] * 3, [r[1] for r in rows[1:]])
        self.assertEqual(["Done", "Fail", "Done"] * 2, [r[3] for r in rows[1:]])
        self.assertIn("password", items[0].extracted_text)
        self.assertEqual(2, summary.failed)
        self.assertEqual(3, len(items[0].results))

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
        self.assertEqual(OcrResultStatus.DONE, writer.results[0].status)
        self.assertEqual(OcrResultStatus.FAIL, writer.results[1].status)

    def test_result_records_effective_default_and_override_languages(self) -> None:
        writer = CapturingWriter(Path("result.csv"))
        use_case = ProcessImagesUseCase(
            FakeImageProcessor(), FakeOcrEngine(), writer, default_language_code="ja",
        )
        items = [ImageItem(Path("default.png")), ImageItem(Path("override.png"), language_code="ch_sim")]
        use_case.execute(items)
        self.assertEqual(["ja", "ch_sim"], [result.language_code for result in writer.results])
        self.assertIsNone(items[0].language_code)


class CsvWriterTests(unittest.TestCase):
    def test_ui_id_is_exported_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = OcrResult("menu.user_name", "인식 결과", 0.9)
            path = CsvResultWriter(Path(directory)).write([result])
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual("menu.user_name", rows[1][0])

    def test_csv_has_required_headers_and_utf8_bom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            output_path = CsvResultWriter(output_directory).write(
                [
                    OcrResult("한글.png", "추출 문자열", 0.93456),
                    OcrResult("빈칸.png", "", None),
                    OcrResult("실패.png", "", None, language_code="ja", processing_failed=True),
                    OcrResult("중국어.png", '你好, "世界"\n두 번째 줄', 0.52, language_code="ch_sim"),
                ]
            )

            raw = output_path.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            with output_path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(
                ["UI ID", "언어", "추출 문자열", "상태", "신뢰도"], rows[0]
            )
            self.assertEqual(["한글.png", "ko", "추출 문자열", "Done", "93.46%"], rows[1])
            self.assertEqual(["빈칸.png", "ko", "", "Need Review", ""], rows[2])
            self.assertEqual(["실패.png", "ja", "", "Fail", ""], rows[3])
            self.assertEqual(["중국어.png", "ch_sim", '你好, "世界"\n두 번째 줄', "Need Review", "52.00%"], rows[4])


if __name__ == "__main__":
    unittest.main()
