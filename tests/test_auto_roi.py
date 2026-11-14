from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox

from ocr_app.domain.models import ROI_COLORS, Roi
from ocr_app.infrastructure.easyocr_roi_detector import EasyOcrRoiDetector, make_roi_candidates
from ocr_app.infrastructure.roi_preset_store import RoiPresetStore
from ocr_app.presentation.main_window import MainWindow
from ocr_app.presentation.roi_draft_dialog import RoiDraftDialog
from ocr_app.presentation.roi_detection_worker import RoiDetectionWorker


class RoiDetectorTests(unittest.TestCase):
    def test_detector_only_loads_craft_and_handles_freeform_boxes(self):
        reader = Mock()
        reader.detect.return_value = (
            [[[2, 22, 4, 14]]],
            [[[[30, 20], [60, 18], [62, 35], [31, 36]]]],
        )
        factory = Mock(return_value=reader)
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(sys.modules, {"easyocr": SimpleNamespace(Reader=factory)}):
                result = EasyOcrRoiDetector(Path(temporary)).detect(np.zeros((40, 80, 3)))
            factory.assert_called_once_with(
                ["en"], gpu=False, recognizer=False, model_storage_directory=temporary,
                download_enabled=False, verbose=False,
            )
        self.assertEqual([(30, 18, 32, 18), (2, 4, 20, 10)],
                         [(r.x, r.y, r.width, r.height) for r in result])

    def test_candidates_clip_deduplicate_and_preserve_existing_tags(self):
        existing = (Roi(20, 20, 40, 20, "ui_1"),)
        result = make_roi_candidates([
            (22, 21, 58, 38), (-2.2, 0.2, 12.1, 12.2),
            (-2.2, 0.2, 12.1, 12.2), (90, 90, 110, 110),
            (4, 4, 5, 5), (float("nan"), 0, 10, 10),
        ], 100, 100, existing)
        self.assertEqual([(0, 0, 13, 13), (90, 90, 10, 10)],
                         [(r.x, r.y, r.width, r.height) for r in result])
        self.assertEqual(["ui_2", "ui_3"], [r.tag for r in result])

    def test_largest_first_removes_nested_boxes_regardless_of_input_order(self):
        boxes = [(10, 10, 20, 20), (10, 10, 90, 90), (10, 10, 60, 60),
                 (120, 20, 160, 60), (120, 20, 160, 60)]
        expected = [(10, 10, 80, 80), (120, 20, 40, 40)]
        for inputs in (boxes, list(reversed(boxes))):
            result = make_roi_candidates(inputs, 200, 100)
            self.assertEqual(expected, [(r.x, r.y, r.width, r.height) for r in result])

    def test_full_containment_includes_touching_edges_but_keeps_partial_overlap(self):
        existing = (Roi(10, 10, 100, 100, "manual"),)
        result = make_roi_candidates([
            (10, 10, 110, 110), (10, 20, 110, 90),  # equal / boundary containment
            (20, 10, 120, 110),  # 90% overlap, but extends beyond the manual ROI
        ], 200, 200, existing)
        self.assertEqual([(20, 10, 100, 100)], [(r.x, r.y, r.width, r.height) for r in result])
        self.assertEqual("manual", existing[0].tag)

    def test_partial_overlap_between_automatic_boxes_keeps_both(self):
        result = make_roi_candidates([(0, 0, 100, 100), (10, 0, 110, 100)], 200, 200)
        self.assertEqual(2, len(result))

    def test_automatic_colors_skip_used_colors_and_cycle_after_palette(self):
        existing = (Roi(0, 50, 10, 10, "manual", ROI_COLORS[0].upper()),)
        boxes = [(20 * i, 0, 20 * i + 10, 10) for i in range(len(ROI_COLORS) + 1)]
        result = make_roi_candidates(boxes, 300, 100, existing)
        self.assertEqual(list(ROI_COLORS[1:]), [r.color for r in result[:7]])
        self.assertEqual(ROI_COLORS[0], result[7].color)
        self.assertEqual(ROI_COLORS[1], result[8].color)

    def test_small_existing_roi_is_preserved_inside_large_new_candidate(self):
        existing = (Roi(20, 20, 10, 10, "manual"),)
        result = make_roi_candidates([(10, 10, 100, 100)], 200, 200, existing)
        self.assertEqual(1, len(result))
        self.assertEqual(Roi(20, 20, 10, 10, "manual"), existing[0])

    def test_worker_reports_failure_without_mutating_existing_rois(self):
        original = (Roi(1, 2, 20, 10, "manual"),)
        worker = RoiDetectionWorker(Path("missing.png"), Path("models"), original, False)
        errors = []
        worker.signals.failed.connect(errors.append)
        with patch("ocr_app.presentation.roi_detection_worker.OpenCvImageLoader") as loader:
            loader.return_value.load.side_effect = ValueError("bad image")
            worker.run()
        self.assertEqual(["bad image"], errors)
        self.assertEqual("manual", original[0].tag)


class AutoRoiUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        image = QPixmap(200, 120)
        image.fill(Qt.GlobalColor.white)
        self.path = self.directory / "image.png"
        image.save(str(self.path))
        self.window = MainWindow()
        self.window._preset_store = RoiPresetStore(self.directory / "presets.json")
        self.window._model.add_paths([self.path, self.directory / "other.png"])
        self.window._table.setCurrentIndex(self.window._model.index(0, 0))
        self.manual = (Roi(1, 1, 30, 15, "manual"),)
        self.window._apply_roi(self.manual)
        self.window._saved_rois = self.manual
        self.candidates = (Roi(60, 30, 70, 20, "ui_1"),)
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window._roi_detection_worker = None
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Discard):
            self.window.close()

    def test_accept_is_local_and_can_be_edited_saved_and_reset(self):
        item, other = self.window._model.items
        self.window._roi_detection_item = item
        with patch("ocr_app.presentation.main_window.RoiDraftDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog.return_value.selected_rois.return_value = self.candidates
            self.window._roi_candidates_found(self.candidates)
        self.assertEqual(self.manual, self.window._static_rois)
        self.assertEqual(self.manual, self.window._effective_rois(other))
        self.assertEqual(self.manual + self.candidates, self.window._effective_rois(item))
        self.assertTrue(item.roi_override)
        self.assertTrue(self.window._has_unsaved_rois)
        edited = self.manual + (replace(self.candidates[0], x=65),)
        self.window._apply_roi(edited)
        self.assertEqual(edited, item.rois)
        menu = self.window._build_roi_menu([0])
        self.assertFalse(menu.actions()[0].isChecked())
        with patch("ocr_app.presentation.main_window.QInputDialog.getText", return_value=("Auto", True)):
            self.assertTrue(self.window._save_preset())
        self.assertEqual(edited, self.window._preset_store.load("Auto"))
        self.assertFalse(self.window._has_unsaved_rois)
        self.window._apply_file_preset([0], None)
        self.assertFalse(item.has_custom_rois)
        self.assertEqual(self.manual, self.window._effective_rois(item))

    def test_cancel_leaves_manual_rois_unchanged(self):
        item = self.window._model.items[0]
        self.window._roi_detection_item = item
        with patch("ocr_app.presentation.main_window.RoiDraftDialog") as dialog:
            dialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            self.window._roi_candidates_found(self.candidates)
        self.assertFalse(item.roi_override)
        self.assertEqual(self.manual, self.window._effective_rois(item))
        self.assertFalse(self.window._has_unsaved_rois)

    def test_candidate_checkboxes_filter_preview_and_disable_empty_apply(self):
        dialog = RoiDraftDialog(self.path, self.manual, self.candidates)
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(self.manual + self.candidates, dialog._preview.rois)
        dialog._list.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual((), dialog.selected_rois())
        self.assertEqual(self.manual, dialog._preview.rois)
        self.assertFalse(dialog._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())

    def test_right_click_unchecks_candidate_but_keeps_colored_row_for_restore(self):
        candidates = (replace(self.candidates[0], color="#ffb347"),)
        dialog = RoiDraftDialog(self.path, self.manual, candidates)
        self.addCleanup(dialog.close)
        dialog.show()
        self.app.processEvents()
        row = dialog._list.item(0)
        self.assertEqual("#ffb347", row.icon().pixmap(14, 14).toImage().pixelColor(7, 7).name())
        position = dialog._preview.mapFromScene(QPointF(90, 40))
        QTest.mouseClick(dialog._preview.viewport(), Qt.MouseButton.RightButton, pos=position)
        self.assertEqual(Qt.CheckState.Unchecked, row.checkState())
        self.assertEqual(1, dialog._list.count())
        self.assertEqual(dialog._list.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text),
                         row.foreground().color())
        self.assertEqual(self.manual, dialog._preview.rois)
        self.assertEqual((), dialog.selected_rois())
        self.assertFalse(dialog._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        row.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(self.manual + candidates, dialog._preview.rois)
        self.assertEqual(candidates, dialog.selected_rois())

    def test_right_click_preserves_manual_roi_and_excludes_topmost_overlapping_candidate(self):
        candidates = self.candidates + (Roi(70, 35, 30, 10, "ui_2", "#72d98b"),)
        dialog = RoiDraftDialog(self.path, self.manual, candidates)
        self.addCleanup(dialog.close)
        dialog.show()
        self.app.processEvents()
        for point in (QPointF(10, 8), QPointF(180, 100)):
            QTest.mouseClick(dialog._preview.viewport(), Qt.MouseButton.RightButton,
                             pos=dialog._preview.mapFromScene(point))
        self.assertEqual(candidates, dialog.selected_rois())
        QTest.mouseClick(dialog._preview.viewport(), Qt.MouseButton.RightButton,
                         pos=dialog._preview.mapFromScene(QPointF(85, 40)))
        self.assertEqual((candidates[0],), dialog.selected_rois())
        self.assertEqual(self.manual + (candidates[0],), dialog._preview.rois)

    def test_background_worker_uses_original_image_and_locks_controls(self):
        self.window._model_download_checkbox.setChecked(True)
        self.window._thread_pool = Mock()
        with patch("ocr_app.presentation.main_window.RoiDetectionWorker") as factory:
            self.window._find_roi_candidates()
            self.assertEqual(self.path.resolve(), factory.call_args.args[0])
            self.assertEqual(self.manual, factory.call_args.args[2])
            self.assertFalse(self.window._auto_roi_button.isEnabled())
            self.assertFalse(self.window._table.isEnabled())
        self.window._roi_detection_failed = Mock()


if __name__ == "__main__":
    unittest.main()
