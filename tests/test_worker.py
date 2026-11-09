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
    def test_missing_language_models_are_download_enabled(self) -> None:
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
                    allow_download=True,
                )


if __name__ == "__main__":
    unittest.main()
