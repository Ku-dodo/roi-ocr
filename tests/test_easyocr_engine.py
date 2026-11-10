from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ocr_app.infrastructure.easyocr_engine import EasyOcrEngine


class EasyOcrEngineTests(unittest.TestCase):
    def test_recognition_uses_tuned_contrast_and_margin(self) -> None:
        reader = Mock()
        reader.readtext.return_value = [
            ([], "  첫 번째  ", 0.8),
            ([], "두   번째", 0.6),
        ]
        reader_type = Mock(return_value=reader)
        easyocr_module = SimpleNamespace(Reader=reader_type)

        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(sys.modules, {"easyocr": easyocr_module}):
                engine = EasyOcrEngine(Path(temporary_directory))
                result = engine.recognize(object())

        reader_type.assert_called_once_with(
            ["ko", "en"],
            gpu=False,
            model_storage_directory=temporary_directory,
            download_enabled=False,
            verbose=False,
        )
        reader.readtext.assert_called_once_with(
            unittest.mock.ANY,
            detail=1,
            paragraph=False,
            contrast_ths=0.05,
            adjust_contrast=0.7,
            add_margin=0.2,
        )
        self.assertEqual("첫 번째 두 번째", result.text)
        self.assertAlmostEqual(0.7, result.confidence)

    def test_recognition_without_text_has_no_confidence(self) -> None:
        reader = Mock()
        reader.readtext.return_value = []
        easyocr_module = SimpleNamespace(Reader=Mock(return_value=reader))

        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(sys.modules, {"easyocr": easyocr_module}):
                engine = EasyOcrEngine(
                    Path(temporary_directory),
                    allow_download=False,
                )
                result = engine.recognize(object())

        self.assertEqual("", result.text)
        self.assertIsNone(result.confidence)


if __name__ == "__main__":
    unittest.main()
