from __future__ import annotations

from dataclasses import replace
import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from ocr_app.domain.models import OcrRecognition, OcrResult, Roi
from ocr_app.infrastructure.roi_preset_store import RoiPresetStore
from ocr_app.presentation.main_window import MainWindow


class FilePresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.window = MainWindow()
        self.addCleanup(self.close_window)
        self.window._preset_store = RoiPresetStore(self.directory / "presets.json")
        self.login = (Roi(10, 20, 100, 40, "user_name"),)
        self.menu = (Roi(30, 40, 200, 60, "menu_name", "#ffb347"),)
        self.window._preset_store.save("Login_Scene", self.login)
        self.window._preset_store.save("Menu_Scene", self.menu)
        self.window._model.add_paths([Path("a.png"), Path("b.png"), Path("c.png")])
        self.window._apply_roi(self.login)

    def close_window(self):
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.window.close()

    def test_explicit_presets_survive_default_changes_and_can_return_to_default(self):
        window = self.window
        window._apply_file_preset([1, 2], "Menu_Scene")
        window._apply_roi((replace(self.login[0], x=50),))
        window._assign_rois_to_items()
        self.assertEqual(window._static_rois, window._model.items[0].rois)
        self.assertEqual(self.menu, window._model.items[1].rois)
        self.assertEqual(self.menu, window._model.items[2].rois)
        self.assertEqual("Menu_Scene", window._model.index(1, 4).data())
        window._apply_file_preset([1], None)
        self.assertEqual(window._static_rois, window._effective_rois(window._model.items[1]))
        self.assertIsNone(window._model.items[1].roi_preset_name)

    def test_switching_images_displays_their_preset_and_retains_results(self):
        window = self.window
        window._apply_file_preset([1], "Menu_Scene")
        window._model.items[1].results = [OcrResult("menu_name", "Menu", 0.99)]
        window._table.setCurrentIndex(window._model.index(1, 0))
        self.assertEqual("menu_name", window._roi_table.item(0, 1).text())
        self.assertEqual("Menu", window._roi_table.item(0, 4).text())
        window._table.setCurrentIndex(window._model.index(0, 0))
        self.assertEqual("user_name", window._roi_table.item(0, 1).text())
        self.assertEqual(self.login, window._display_rois())
        self.assertEqual("Menu", window._model.items[1].results[0].extracted_text)

    def test_right_click_preserves_multiselection_and_nested_actions_apply_only_selected(self):
        window = self.window
        window.show()
        self.application.processEvents()
        window._table.selectAll()
        position = window._table.visualRect(window._model.index(1, 0)).center()
        QTest.mouseClick(window._table.viewport(), Qt.MouseButton.RightButton, pos=position)
        self.assertEqual(3, len(window._table.selectionModel().selectedRows()))
        menu = window._build_file_context_menu([0, 2])
        self.addCleanup(menu.deleteLater)
        self.assertEqual(["ROI 변경", "언어 변경"], [action.text() for action in menu.actions()])
        roi_menu, language_menu = [action.menu() for action in menu.actions()]
        next(action for action in roi_menu.actions() if action.data() == "Menu_Scene").trigger()
        next(action for action in language_menu.actions() if action.data() == "ja").trigger()
        self.assertEqual(["Menu_Scene", None, "Menu_Scene"], [i.roi_preset_name for i in window._model.items])
        self.assertEqual(["ja", None, "ja"], [i.language_code for i in window._model.items])
        language_menu.actions()[0].trigger()
        roi_menu.actions()[0].trigger()
        self.assertTrue(all(i.roi_preset_name is None and i.language_code is None for i in window._model.items))

    def test_missing_preset_assignment_is_atomic(self):
        window = self.window
        window._apply_file_preset([0], "Login_Scene")
        with patch.object(QMessageBox, "warning") as warning:
            window._apply_file_preset([0, 1, 2], "Missing")
        warning.assert_called_once()
        self.assertEqual(["Login_Scene", None, None], [i.roi_preset_name for i in window._model.items])

    def test_individual_edits_are_saved_separately_and_keep_default_and_other_images(self):
        window = self.window
        window._saved_rois = self.login
        window._apply_file_preset([0, 1], "Menu_Scene")
        window._table.setCurrentIndex(window._model.index(0, 0))
        edited = (replace(self.menu[0], x=75),)
        window._apply_roi(edited)
        self.assertEqual(self.login, window._static_rois)
        self.assertEqual(self.menu, window._model.items[1].rois)
        self.assertTrue(window._has_unsaved_rois)
        self.assertIn("*", window._model.index(0, 4).data())
        with patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Custom_Menu", True)):
            self.assertTrue(window._save_unsaved_rois())
        self.assertFalse(window._has_unsaved_rois)
        self.assertEqual(edited, window._preset_store.load("Custom_Menu"))
        self.assertEqual(self.menu, window._preset_store.load("Menu_Scene"))

    def test_explicit_presets_run_without_default_roi_and_export_their_own_ui_ids(self):
        window = self.window
        window._apply_roi(())
        window._apply_file_preset([0, 2], "Login_Scene")
        window._apply_file_preset([1], "Menu_Scene")
        window._thread_pool = Mock()
        window._model_download_checkbox.setChecked(True)
        window._run_ocr()
        worker = window._worker
        self.assertIsNotNone(worker)
        worker._result_directory = self.directory
        with (
            patch("ocr_app.presentation.worker.OpenCvImageProcessor"),
            patch("ocr_app.presentation.worker.EasyOcrEngine") as engine,
            patch.object(QMessageBox, "information"),
        ):
            engine.return_value.recognize.return_value = OcrRecognition("text", 0.99)
            worker.run()
        with next(self.directory.glob("ocr_result_*.csv")).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(["user_name", "menu_name", "user_name"], [row[0] for row in rows[1:]])

    def test_loading_default_preset_does_not_replace_file_override(self):
        window = self.window
        window._apply_file_preset([0], "Menu_Scene")
        window._table.setCurrentIndex(window._model.index(0, 0))
        window._reload_presets("Login_Scene")
        window._load_preset()
        self.assertEqual(self.login, window._static_rois)
        self.assertEqual(self.menu, window._display_rois())
        self.assertEqual("menu_name", window._roi_table.item(0, 1).text())

    def test_selecting_preset_before_adding_image_immediately_draws_gizmos(self):
        window = self.window
        window._clear_all()
        window._apply_roi(())
        window._reload_presets()
        window._preset_combo.setCurrentIndex(window._preset_combo.findData("Menu_Scene"))
        window._preset_combo.activated.emit(window._preset_combo.currentIndex())
        path = self.directory / "new_image.png"
        pixmap = QPixmap(400, 300)
        pixmap.fill(Qt.GlobalColor.white)
        self.assertTrue(pixmap.save(str(path)))
        window._add_image_paths([path])
        self.application.processEvents()
        self.assertEqual(self.menu, window._static_rois)
        self.assertEqual(self.menu, window._preview.rois)
        self.assertEqual(1, len(window._preview._roi_items))
        self.assertEqual(1, len(window._preview._handles))
        self.assertEqual("menu_name", window._preview._labels[0].toolTip())
        self.assertEqual("menu_name", window._roi_table.item(0, 1).text())

    def test_refreshing_preset_list_does_not_replace_unsaved_default_roi(self):
        window = self.window
        edited = (replace(self.login[0], width=150),)
        window._apply_roi(edited)
        window._reload_presets("Menu_Scene")
        self.assertEqual(edited, window._static_rois)
        self.assertTrue(window._has_unsaved_rois)
