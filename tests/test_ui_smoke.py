from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCompleter, QMessageBox

from ocr_app.domain.models import ImageStatus, OcrResult, Roi
from ocr_app.infrastructure.roi_preset_store import RoiPresetStore
from ocr_app.presentation.image_drop_table import ImageDropTable
from ocr_app.presentation.main_window import MainWindow


class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def close_window(self, window):
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            window.close()

    def test_close_without_roi_changes_does_not_prompt(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        with patch.object(QMessageBox, "warning") as warning:
            self.assertTrue(window.close())
        warning.assert_not_called()

    def test_close_cancel_and_discard_unsaved_roi_changes(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        roi = Roi(10, 20, 100, 40, "user_name")
        window._apply_roi((roi,))
        window.show()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as warning:
            self.assertFalse(window.close())
        self.assertEqual(QMessageBox.StandardButton.Cancel, warning.call_args.args[4])
        self.assertTrue(window.isVisible())
        self.assertEqual((roi,), window._static_rois)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.assertTrue(window.close())

    def test_close_saves_roi_preset_before_exiting(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window._preset_store = RoiPresetStore(Path(directory) / "presets.json")
            roi = Roi(10, 20, 100, 40, "user_name")
            window._apply_roi((roi,))
            with (
                patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save),
                patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Login_Scene", True)),
            ):
                self.assertTrue(window.close())
            self.assertEqual((roi,), window._preset_store.load("Login_Scene"))
            self.assertFalse(window._has_unsaved_rois)

    def test_cancelled_or_failed_save_keeps_window_open_and_roi_dirty(self):
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window._preset_store = RoiPresetStore(Path(directory) / "presets.json")
            roi = Roi(10, 20, 100, 40, "user_name")
            window._apply_roi((roi,))
            window.show()
            with (
                patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Save),
                patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("", False)),
            ):
                self.assertFalse(window.close())
            with (
                patch.object(QMessageBox, "warning", side_effect=[QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Ok]),
                patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Login_Scene", True)),
                patch.object(window._preset_store, "save", side_effect=OSError("write failed")),
            ):
                self.assertFalse(window.close())
            self.assertTrue(window.isVisible())
            self.assertTrue(window._has_unsaved_rois)
            self.assertEqual((roi,), window._static_rois)

    def test_loading_or_saving_resets_dirty_baseline_but_edits_and_deletion_do_not(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window._preset_store = RoiPresetStore(Path(directory) / "presets.json")
            roi = Roi(10, 20, 100, 40, "user_name")
            window._preset_store.save("Login_Scene", (roi,))
            window._reload_presets("Login_Scene")
            window._load_preset()
            self.assertFalse(window._has_unsaved_rois)
            for updated in (replace(roi, x=20), replace(roi, width=110), replace(roi, tag="name"),
                            replace(roi, color="#ffb347")):
                window._apply_roi((updated,))
                self.assertTrue(window._has_unsaved_rois)
                window._apply_roi((roi,))
                self.assertFalse(window._has_unsaved_rois)
            window._apply_roi(())
            self.assertTrue(window._has_unsaved_rois)
            window._apply_roi((roi,))
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                window._delete_preset()
            self.assertTrue(window._has_unsaved_rois)

    def test_clearing_images_preserves_unsaved_roi_definitions(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("sample.png")])
        roi = Roi(10, 20, 100, 40, "user_name")
        window._apply_roi((roi,))
        window._clear_all()
        self.assertEqual((roi,), window._static_rois)
        self.assertEqual((roi,), window._preview.rois)
        self.assertTrue(window._has_unsaved_rois)

    def test_pending_tag_edit_is_committed_before_close_warning(self):
        from PySide6.QtWidgets import QLineEdit
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        roi = Roi(10, 20, 100, 40, "user_name")
        window._apply_roi((roi,))
        window._saved_rois = (roi,)
        window.show()
        self.application.processEvents()
        window._roi_table.editItem(window._roi_table.item(0, 1))
        editor = window._roi_table.findChild(QLineEdit)
        self.assertIsNotNone(editor)
        editor.setFocus()
        editor.selectAll()
        QTest.keyClicks(editor, "display_name")
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Cancel) as warning:
            self.assertFalse(window.close())
        warning.assert_called_once()
        self.assertEqual("display_name", window._static_rois[0].tag)

    def test_main_window_can_be_constructed(self) -> None:
        window = MainWindow()
        self.assertEqual("이미지 OCR 도구", window.windowTitle())
        self.assertEqual(6, window._model.columnCount())
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
        self.assertFalse(window._model_download_checkbox.isChecked())
        self.assertEqual(
            [1, 2, 4],
            [window._scale_combo.itemData(index) for index in range(window._scale_combo.count())],
        )
        self.close_window(window)

    def test_roi_table_shows_selected_image_progress_results_and_errors(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        self.assertFalse(hasattr(window, "_result_text"))
        self.assertEqual(5, window._roi_table.columnCount())
        window._model.add_paths([Path("ko.png"), Path("en.png")])
        rois = (Roi(0, 0, 10, 10, "name"), Roi(20, 0, 10, 10, "button"))
        window._apply_roi(rois)
        window._table.setCurrentIndex(window._model.index(0, 0))
        korean, english = window._model.items
        korean.status = ImageStatus.PROCESSING
        korean.active_roi_id = "button"
        korean.results = [OcrResult("name", "사용자", 0.99)]
        window._ocr_progress(0, 2, korean)
        self.assertEqual("완료", window._roi_table.item(0, 3).text())
        self.assertEqual("사용자", window._roi_table.item(0, 4).text())
        self.assertEqual("진행 중", window._roi_table.item(1, 3).text())
        english.results = [OcrResult("name", "User", 0.5, "en"),
                           OcrResult("button", "", None, "en", True, "broken ROI")]
        window._table.setCurrentIndex(window._model.index(1, 0))
        self.assertEqual("User", window._roi_table.item(0, 4).text())
        self.assertEqual("검토 필요", window._roi_table.item(0, 3).text())
        self.assertEqual("실패", window._roi_table.item(1, 3).text())
        self.assertIn("broken ROI", window._roi_table.item(1, 4).toolTip())
        window._clear_previous_results()
        self.assertEqual("대기", window._roi_table.item(0, 3).text())
        self.assertEqual("", window._roi_table.item(0, 4).text())

    def test_preset_save_load_and_delete_through_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window._preset_store = RoiPresetStore(path)
            rois = (Roi(0, 0, 10, 10, "user_name"), Roi(20, 0, 10, 10, "button", "#ffb347"))
            window._apply_roi(rois)
            with patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Login_Scene", True)):
                window._preset_save_button.click()
            restored = MainWindow()
            self.addCleanup(self.close_window, restored)
            restored._preset_store = RoiPresetStore(path)
            restored._reload_presets("Login_Scene")
            restored._preset_load_button.click()
            self.assertEqual(rois, restored._static_rois)
            self.assertEqual(rois, restored._preview.rois)
            self.assertEqual("user_name", restored._roi_table.item(0, 1).text())
            restored._set_controls_enabled(False)
            self.assertFalse(restored._preset_load_button.isEnabled())
            restored._set_controls_enabled(True)
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                restored._preset_delete_button.click()
            self.assertEqual([], RoiPresetStore(path).names())
            self.assertEqual(rois, restored._static_rois)

    def test_default_language_changes_only_inherited_files(self) -> None:
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("default.png"), Path("explicit.png")])
        window._model.set_language_for_rows([1], "ko")
        window._language_combo.setCurrentIndex(window._language_combo.findData("ch_sim"))
        self.assertEqual("기본값 · 중국어(간체)", window._model.index(0, 3).data())
        self.assertEqual("한국어", window._model.index(1, 3).data())
        window._model.set_language_for_rows([1], None)
        self.assertEqual("기본값 · 중국어(간체)", window._model.index(1, 3).data())
        window._language_combo.setCurrentIndex(window._language_combo.findData("ko"))

    def test_bulk_language_editor_applies_choice_and_restores_default(self) -> None:
        from ocr_app.presentation.searchable_combo_box import SearchableComboBox

        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("first.png"), Path("second.png")])
        window.show()
        window._table.selectAll()
        for code in ("ch_sim", None):
            window._file_language_button.click()
            self.application.processEvents()
            editor = window._table.findChild(SearchableComboBox)
            self.assertIsNotNone(editor)
            editor.setCurrentIndex(editor.findData(code))
            editor.activated.emit(editor.currentIndex())
            self.application.processEvents()
            self.assertEqual([code, code], [i.language_code for i in window._model.items])
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_override_model_is_checked_even_when_default_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            models = Path(temporary_directory)
            (models / "craft_mlt_25k.pth").touch()
            (models / "korean_g2.pth").touch()
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window._language_combo.setCurrentIndex(window._language_combo.findData("ko"))
            window._model.add_paths([Path("chinese.png")])
            window._model.set_language_for_rows([0], "ch_sim")
            window._thread_pool = Mock()
            with (
                patch("ocr_app.presentation.main_window.model_directory", return_value=models),
                patch.object(QMessageBox, "warning") as warning,
            ):
                window._apply_roi((Roi(0, 0, 10, 10, "user_name"),))
                window._run_ocr()
            self.assertIn("중국어(간체)", warning.call_args.args[2])
            window._thread_pool.start.assert_not_called()

    def test_language_cell_click_opens_editor_and_escape_preserves_override(self) -> None:
        from ocr_app.presentation.searchable_combo_box import SearchableComboBox

        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("first.png")])
        window._model.set_language_for_rows([0], "ja")
        window.show()
        self.application.processEvents()
        index = window._model.index(0, 3)
        QTest.mouseClick(window._table.viewport(), Qt.MouseButton.LeftButton,
                         pos=window._table.visualRect(index).center())
        editor = window._table.findChild(SearchableComboBox)
        self.assertIsNotNone(editor)
        editor.setCurrentIndex(editor.findData("ko"))
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertEqual("ja", window._model.items[0].language_code)

    def test_language_popup_fits_labels_even_when_column_is_narrow(self) -> None:
        from ocr_app.presentation.searchable_combo_box import SearchableComboBox

        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("first.png")])
        window.show()
        self.application.processEvents()
        self.assertGreaterEqual(window._table.columnWidth(3), 190)
        window._table.setColumnWidth(3, 80)
        window._table.selectRow(0)
        window._file_language_button.click()
        editor = window._table.findChild(SearchableComboBox)
        editor.showPopup()
        self.application.processEvents()
        longest_label = max(editor.view().fontMetrics().horizontalAdvance(editor.itemText(row))
                            for row in range(editor.count()))
        self.assertGreater(editor.view().viewport().width(), longest_label)
        self.assertGreater(editor.view().width(), editor.width())
        self.assertGreater(editor.completer().popup().minimumWidth(), longest_label)
        editor.hidePopup()
        QTest.keyClick(editor, Qt.Key.Key_Escape)

    def test_opening_bulk_editor_without_choosing_preserves_mixed_languages(self) -> None:
        from ocr_app.presentation.searchable_combo_box import SearchableComboBox

        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window._model.add_paths([Path("first.png"), Path("second.png")])
        window._model.set_language_for_rows([1], "ch_sim")
        window.show()
        window._table.selectAll()
        window._file_language_button.click()
        editor = window._table.findChild(SearchableComboBox)
        window._language_delegate.commitData.emit(editor)
        window._language_delegate.closeEditor.emit(editor)
        self.assertEqual([None, "ch_sim"], [i.language_code for i in window._model.items])

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
        self.close_window(window)

    def test_settings_hover_stays_open_when_entering_panel_and_closes_on_leave(self) -> None:
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window.show()
        self.application.processEvents()
        popup = window._settings_popup
        self.assertFalse(popup.isVisible())
        QApplication.sendEvent(window._settings_button, QEvent(QEvent.Type.Enter))
        QTest.qWait(230)
        self.assertTrue(popup.isVisible())
        for control in (
            window._model_download_checkbox, window._scale_combo, window._preprocess_checkbox,
        ):
            self.assertTrue(popup.isAncestorOf(control))
        QApplication.sendEvent(window._settings_button, QEvent(QEvent.Type.Leave))
        QApplication.sendEvent(popup, QEvent(QEvent.Type.Enter))
        QTest.qWait(350)
        self.assertTrue(popup.isVisible())
        with patch(
            "ocr_app.presentation.settings_popover.QCursor.pos",
            return_value=window.mapToGlobal(QPoint(10, 400)),
        ):
            QApplication.sendEvent(popup, QEvent(QEvent.Type.Leave))
            QTest.qWait(350)
        self.assertFalse(popup.isVisible())

    def test_settings_click_escape_and_outside_click(self) -> None:
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window.show()
        self.application.processEvents()
        QTest.mouseClick(window._settings_button, Qt.MouseButton.LeftButton)
        self.assertTrue(window._settings_popup.isVisible())
        QTest.keyClick(window._settings_button, Qt.Key.Key_Escape)
        self.assertFalse(window._settings_popup.isVisible())
        window._settings_button.click()
        QTest.mouseClick(window._roi_label, Qt.MouseButton.LeftButton)
        self.assertFalse(window._settings_popup.isVisible())

    def test_settings_remain_open_while_scale_dropdown_is_used(self) -> None:
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window.show()
        self.application.processEvents()
        window._model.add_paths([Path("first.png"), Path("second.png")])
        window._table.selectAll()
        window._settings_button.click()
        window._scale_combo.showPopup()
        with patch(
            "ocr_app.presentation.settings_popover.QCursor.pos",
            return_value=window.mapToGlobal(QPoint(10, 400)),
        ):
            QApplication.sendEvent(window._settings_popup, QEvent(QEvent.Type.Leave))
            QTest.qWait(350)
            self.assertTrue(window._settings_popup.isVisible())
            self.assertTrue(window._scale_combo.view().isVisible())
        QTest.keyClick(window._scale_combo, Qt.Key.Key_Down)
        QTest.keyClick(window._scale_combo, Qt.Key.Key_Return)
        self.assertTrue(all(item.scale_factor == 2 for item in window._model.items))
        self.assertTrue(window._settings_popup.isVisible())

    def test_settings_close_and_cannot_reopen_during_ocr(self) -> None:
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        window.show()
        self.application.processEvents()
        window._settings_button.click()
        self.assertTrue(window._settings_popup.isVisible())
        window._set_controls_enabled(False)
        self.assertFalse(window._settings_popup.isVisible())
        controls = (
            window._model_download_checkbox, window._scale_combo, window._preprocess_checkbox,
        )
        self.assertTrue(all(not control.isEnabled() for control in controls))
        window._settings_popup.show_panel()
        self.assertFalse(window._settings_popup.isVisible())
        window._set_controls_enabled(True)
        self.assertTrue(all(control.isEnabled() for control in controls))
        window._settings_button.click()
        self.assertTrue(window._settings_popup.isVisible())

    def test_missing_language_model_requires_download_opt_in(self) -> None:
        window = MainWindow()
        window._language_combo.setCurrentIndex(window._language_combo.findData("ja"))
        self.assertIn("자동 다운로드 OFF", window._status_label.text())
        window._model_download_checkbox.setChecked(True)
        self.assertIn("모델 자동 다운로드", window._status_label.text())
        window._language_combo.setCurrentIndex(window._language_combo.findData("ko"))
        self.close_window(window)

    def test_ocr_does_not_start_when_models_are_missing_and_download_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            window = MainWindow()
            window._model.add_paths([Path("sample.png")])
            window._thread_pool = Mock()

            with (
                patch(
                    "ocr_app.presentation.main_window.model_directory",
                    return_value=Path(temporary_directory),
                ),
                patch.object(QMessageBox, "warning") as warning,
            ):
                window._apply_roi((Roi(0, 0, 10, 10, "user_name"),))
                window._run_ocr()

            warning.assert_called_once()
            window._thread_pool.start.assert_not_called()
            self.assertIsNone(window._worker)
            self.close_window(window)

    def test_ocr_worker_receives_download_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            window = MainWindow()
            window._model.add_paths([Path("sample.png")])
            window._model_download_checkbox.setChecked(True)
            window._thread_pool = Mock()

            with patch(
                "ocr_app.presentation.main_window.model_directory",
                return_value=Path(temporary_directory),
            ):
                window._apply_roi((Roi(0, 0, 10, 10, "user_name"),))
                window._run_ocr()

            window._thread_pool.start.assert_called_once_with(window._worker)
            self.assertTrue(window._worker._allow_model_download)
            self.close_window(window)

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
        self.close_window(window)

    def test_default_rois_are_assigned_to_inherited_images_for_ocr(self) -> None:
        window = MainWindow()
        window._model.add_paths([Path("first.png"), Path("second.png")])
        static_roi = Roi(10, 20, 100, 50)

        window._apply_roi((static_roi,))

        self.assertTrue(all(item.rois == () for item in window._model.items))
        window._assign_rois_to_items()
        self.assertTrue(
            all(item.rois == (static_roi,) for item in window._model.items)
        )
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            window._clear_roi_button.click()
        self.assertEqual((), window._static_rois)
        self.close_window(window)

    def test_tags_edit_and_reject_duplicates_and_clear_all(self) -> None:
        from PySide6.QtGui import QColor
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        self.assertFalse(hasattr(window, "_include_extension_checkbox"))
        rois = (Roi(0, 0, 10, 10, "user_name"), Roi(20, 20, 10, 10, "password", "#ffb347"))
        window._apply_roi(rois)
        window._roi_table.item(0, 1).setText("display_name")
        self.assertEqual("display_name", window._static_rois[0].tag)
        self.assertEqual(window._static_rois, window._preview.rois)
        for invalid in ("", "password"):
            with patch.object(QMessageBox, "warning") as warning:
                window._roi_table.item(0, 1).setText(invalid)
            warning.assert_called_once()
            self.assertEqual("display_name", window._roi_table.item(0, 1).text())
        with patch("ocr_app.presentation.main_window.QColorDialog.getColor", return_value=QColor("#00ff00")):
            window._roi_color_changed(0, 0)
        self.assertEqual("#00ff00", window._static_rois[0].color)
        window._set_controls_enabled(False)
        self.assertFalse(window._preview.isEnabled())
        self.assertFalse(window._roi_table.isEnabled())
        window._set_controls_enabled(True)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            window._clear_roi_button.click()
        self.assertEqual((), window._static_rois)
        self.assertEqual(0, window._roi_table.rowCount())

    def test_dragged_roi_updates_table_preserves_results_and_can_be_saved(self):
        from PySide6.QtGui import QPixmap
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            pixmap = QPixmap(1000, 800)
            pixmap.fill(Qt.GlobalColor.white)
            pixmap.save(str(path))
            window = MainWindow()
            self.addCleanup(self.close_window, window)
            window.show()
            window._add_image_paths([path])
            original = Roi(200, 200, 200, 100, "user_name")
            window._preview.set_rois((original,))
            window._apply_roi((original,))
            self.application.processEvents()
            window._model.items[0].results = [OcrResult("user_name", "old result", 0.9)]
            preview = window._preview
            start = preview.mapFromScene(QPointF(300, 250))
            end = start + QPoint(30, 25)
            QTest.mousePress(preview.viewport(), Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(preview.viewport(), end)
            QTest.mouseRelease(preview.viewport(), Qt.MouseButton.LeftButton, pos=end)
            moved = window._static_rois[0]
            self.assertNotEqual(original, moved)
            self.assertEqual((moved,), preview.rois)
            self.assertEqual(f"{moved.x}, {moved.y}, {moved.width}, {moved.height}",
                             window._roi_table.item(0, 2).text())
            self.assertEqual("완료", window._roi_table.item(0, 3).text())
            self.assertEqual("old result", window._roi_table.item(0, 4).text())
            self.assertEqual([OcrResult("user_name", "old result", 0.9)], window._model.items[0].results)
            window._preset_store = RoiPresetStore(Path(directory) / "presets.json")
            with patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Moved", True)):
                window._save_preset()
            self.assertEqual((moved,), window._preset_store.load("Moved"))

    def test_clear_all_rois_requires_confirmation_and_preserves_previous_results(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        roi = Roi(10, 10, 100, 40, "user_name")
        window._model.add_paths([Path("sample.png")])
        window._preview.set_rois((roi,))
        window._apply_roi((roi,))
        result = OcrResult("user_name", "previous result", 0.9)
        window._model.items[0].results = [result]
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No) as warning:
            window._clear_roi_button.click()
        self.assertEqual(QMessageBox.StandardButton.No, warning.call_args.args[4])
        self.assertEqual((roi,), window._static_rois)
        self.assertEqual((roi,), window._preview.rois)
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            window._clear_roi_button.click()
        self.assertEqual((), window._static_rois)
        self.assertEqual([result], window._model.items[0].results)

    def test_resizing_preserves_all_images_results_until_ocr_is_run_again(self):
        window = MainWindow()
        self.addCleanup(self.close_window, window)
        roi = Roi(10, 10, 100, 40, "user_name")
        resized = Roi(10, 10, 150, 60, "user_name")
        window._model.add_paths([Path("ko.png"), Path("en.png")])
        window._apply_roi((roi,))
        for item, text, code in zip(window._model.items, ("이전 결과", "old result"), ("ko", "en")):
            item.results = [OcrResult("user_name", text, 0.9, code)]
            item.extracted_text = text
            item.confidence = 0.9
            item.status = ImageStatus.COMPLETED
        previous = [list(item.results) for item in window._model.items]
        window._apply_roi((resized,))
        self.assertEqual(previous, [item.results for item in window._model.items])
        self.assertTrue(all(item.confidence == 0.9 for item in window._model.items))
        for row, expected in enumerate(("이전 결과", "old result")):
            window._table.setCurrentIndex(window._model.index(row, 0))
            self.assertEqual(expected, window._roi_table.item(0, 4).text())
            self.assertEqual("완료", window._roi_table.item(0, 3).text())
        window._thread_pool = Mock()
        window._model_download_checkbox.setChecked(True)
        window._run_ocr()
        window._thread_pool.start.assert_called_once()
        self.assertTrue(all(item.rois == (resized,) for item in window._model.items))
        self.assertTrue(all(item.results == [] and item.extracted_text == "" for item in window._model.items))
        self.assertEqual("대기", window._roi_table.item(0, 3).text())

    def test_drop_data_accepts_only_existing_local_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            image_path = directory / "sample.PNG"
            text_path = directory / "notes.txt"
            image_path.touch()
            text_path.touch()
            mime_data = QMimeData()
            mime_data.setUrls(
                [
                    QUrl.fromLocalFile(str(image_path)),
                    QUrl.fromLocalFile(str(text_path)),
                    QUrl("https://example.com/remote.png"),
                ]
            )

            self.assertEqual((image_path,), ImageDropTable.image_paths(mime_data))

    def test_dropped_paths_use_the_same_addition_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            first_path = Path(temporary_directory) / "first.png"
            second_path = Path(temporary_directory) / "second.png"
            first_path.touch()
            second_path.touch()
            mime_data = QMimeData()
            mime_data.setUrls(
                [
                    QUrl.fromLocalFile(str(first_path)),
                    QUrl.fromLocalFile(str(second_path)),
                ]
            )
            drop_event = QDropEvent(
                QPointF(),
                Qt.DropAction.CopyAction,
                mime_data,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            window = MainWindow()

            window._table.dropEvent(drop_event)

            self.assertTrue(drop_event.isAccepted())
            self.assertEqual(2, len(window._model.items))
            self.assertEqual(0, window._table.currentIndex().row())
            self.assertIn("2개", window._status_label.text())
            self.close_window(window)


if __name__ == "__main__":
    unittest.main()
