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


class OcrWorkerTests(unittest.TestCase):
    def test_csv_writer_receives_file_extension_setting(self) -> None:
        for include in (True, False):
            with (
                self.subTest(include_file_extension=include),
                patch("ocr_app.presentation.worker.EasyOcrEngine"),
                patch("ocr_app.presentation.worker.ProcessImagesUseCase"),
                patch("ocr_app.presentation.worker.CsvResultWriter") as writer_type,
            ):
                worker = OcrWorker(
                    items=[], model_directory=Path("models"),
                    result_directory=Path("result"), languages=("ko", "en"),
                    include_file_extension=include,
                )
                worker.run()
                writer_type.assert_called_once_with(Path("result"), include_file_extension=include)

    def test_model_download_is_disabled_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory)
            with (
                patch("ocr_app.presentation.worker.EasyOcrEngine") as engine_type,
                patch("ocr_app.presentation.worker.ProcessImagesUseCase") as use_case_type,
            ):
                use_case_type.return_value.execute.return_value = object()
                worker = OcrWorker(
                    items=[],
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
                patch("ocr_app.presentation.worker.ProcessImagesUseCase") as use_case_type,
            ):
                use_case_type.return_value.execute.return_value = object()
                worker = OcrWorker(
                    items=[],
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


if __name__ == "__main__":
    unittest.main()
