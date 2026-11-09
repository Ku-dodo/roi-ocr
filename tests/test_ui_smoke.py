from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCompleter

from ocr_app.domain.models import ImageStatus, Roi
from ocr_app.presentation.main_window import MainWindow


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_main_window_can_be_constructed(self) -> None:
        window = MainWindow()
        self.assertEqual("이미지 OCR 도구", window.windowTitle())
        self.assertEqual(4, window._model.columnCount())
        self.assertEqual(86, window._language_combo.count())
        self.assertGreaterEqual(window._language_combo.findData("ko"), 0)
        self.assertTrue(window._language_combo.isEditable())
        self.assertEqual(
            QCompleter.CompletionMode.PopupCompletion,
            window._language_combo.completer().completionMode(),
        )
        self.assertEqual(
            Qt.MatchFlag.MatchContains,
            window._language_combo.completer().filterMode(),
        )
        window.close()

    def test_language_combo_searches_name_and_rejects_unknown_text(self) -> None:
        window = MainWindow()
        combo = window._language_combo
        korean_index = combo.findData("ko")
        combo.setCurrentIndex(korean_index)

        combo.completer().setCompletionPrefix("일본")
        self.assertEqual(1, combo.completer().completionCount())
        combo.completer().setCompletionPrefix("ja")
        self.assertEqual(1, combo.completer().completionCount())

        combo.setEditText("지원하지 않는 언어")
        combo.lineEdit().editingFinished.emit()
        self.assertEqual("ko", combo.currentData())
        window.close()

    def test_missing_language_model_is_marked_for_automatic_download(self) -> None:
        window = MainWindow()
        window._language_combo.setCurrentIndex(window._language_combo.findData("ja"))
        self.assertIn("자동 다운로드", window._status_label.text())
        window._language_combo.setCurrentIndex(window._language_combo.findData("ko"))
        window.close()

    def test_previous_result_is_cleared_before_rerun(self) -> None:
        window = MainWindow()
        window._model.add_paths([Path("previous-result.png")])
        item = window._model.items[0]
        item.extracted_text = "이전 OCR 결과"
        item.confidence = 0.91
        item.error_message = "이전 오류"
        item.status = ImageStatus.FAILED

        window._clear_previous_results()

        self.assertEqual("", item.extracted_text)
        self.assertIsNone(item.confidence)
        self.assertEqual("", item.error_message)
        self.assertEqual(ImageStatus.READY, item.status)
        window.close()

    def test_static_roi_is_assigned_to_every_image_for_ocr(self) -> None:
        window = MainWindow()
        window._model.add_paths([Path("first.png"), Path("second.png")])
        static_roi = Roi(10, 20, 100, 50)

        window._apply_roi(static_roi)

        self.assertTrue(all(item.roi is None for item in window._model.items))
        window._assign_static_roi_to_items()
        self.assertTrue(
            all(item.roi == static_roi for item in window._model.items)
        )
        window.close()


if __name__ == "__main__":
    unittest.main()
