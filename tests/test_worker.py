from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ocr_app.presentation.worker import OcrWorker
from ocr_app.domain.models import ImageItem, ImageStatus, OcrRecognition


class OcrWorkerTests(unittest.TestCase):
    def test_model_download_is_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)
            with (
                patch("ocr_app.presentation.worker.EasyOcrEngine") as engine_type,
                patch("ocr_app.presentation.worker.OpenCvImageProcessor"),
            ):
                engine_type.return_value.recognize.return_value = OcrRecognition("text", 0.9)
                worker = OcrWorker(
                    items=[ImageItem(path / "sample.png")],
                    model_directory=path / "models",
                    result_directory=path / "result",
                    languages=("ja", "en"),
                )

                worker.run()

                engine_type.assert_called_once_with(
                    model_directory=path / "models",
                    languages=("ja", "en"),
                    use_gpu=False,
                    allow_download=False,
                )

    def test_model_download_can_be_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)
            with (
                patch("ocr_app.presentation.worker.EasyOcrEngine") as engine_type,
                patch("ocr_app.presentation.worker.OpenCvImageProcessor"),
            ):
                engine_type.return_value.recognize.return_value = OcrRecognition("text", 0.9)
                worker = OcrWorker(
                    items=[ImageItem(path / "sample.png")],
                    model_directory=path / "models",
                    result_directory=path / "result",
                    languages=("ja", "en"),
                    allow_model_download=True,
                )

                worker.run()

                engine_type.assert_called_once_with(
                    model_directory=path / "models",
                    languages=("ja", "en"),
                    use_gpu=False,
                    allow_download=True,
                )

    def test_mixed_languages_use_overrides_and_keep_csv_order(self) -> None:
        import csv

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)
            items = [
                ImageItem(path / "chinese.png", language_code="ch_sim"),
                ImageItem(path / "korean.png"),
                ImageItem(path / "korean2.png", language_code="ko"),
                ImageItem(path / "english.png", language_code="en"),
            ]
            with (
                patch("ocr_app.presentation.worker.EasyOcrEngine") as engine_type,
                patch("ocr_app.presentation.worker.OpenCvImageProcessor"),
            ):
                engine_type.side_effect = lambda **kw: type("Reader", (), {
                    "recognize": lambda _, image: OcrRecognition(kw["languages"][0], 0.9)
                })()
                worker = OcrWorker(items, path, path, languages=("ko", "en"))
                worker.run()
            self.assertEqual(["ch_sim", "ko", "ko", "en"], [i.results[0].extracted_text for i in items])
            self.assertTrue(all(i.status == ImageStatus.COMPLETED for i in items))
            self.assertEqual(3, engine_type.call_count)
            with next(path.glob("*.csv")).open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(["full_image"] * len(items), [r[0] for r in rows[1:]])
            self.assertEqual(["ch_sim", "ko", "ko", "en"], [r[1] for r in rows[1:]])
            self.assertTrue(all(r[3] == "Done" for r in rows[1:]))

    def test_model_load_failure_does_not_stop_other_languages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)
            items = [ImageItem(path / "bad.png", language_code="ja"), ImageItem(path / "good.png")]
            with (
                patch("ocr_app.presentation.worker.EasyOcrEngine") as engine_type,
                patch("ocr_app.presentation.worker.OpenCvImageProcessor"),
            ):
                from unittest.mock import Mock
                engine_type.side_effect = [RuntimeError("model unavailable"), Mock(
                    recognize=Mock(return_value=OcrRecognition("ok", 0.9))
                )]
                worker = OcrWorker(items, path, path, languages=("ko", "en"))
                worker.run()
            self.assertEqual(ImageStatus.FAILED, items[0].status)
            self.assertEqual(ImageStatus.COMPLETED, items[1].status)
            import csv
            with next(path.glob("*.csv")).open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(["ja", "", "Fail", ""], rows[1][1:])
            self.assertEqual(["ko", "ok", "Done", "90.00%"], rows[2][1:])


if __name__ == "__main__":
    unittest.main()
