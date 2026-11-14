from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QFocusEvent, QPixmap, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from ocr_app.domain.models import Roi
from ocr_app.presentation.image_preview import ImagePreview


class ImagePreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "sample.png"
        pixmap = QPixmap(1600, 1200)
        pixmap.fill(Qt.GlobalColor.white)
        self.assertTrue(pixmap.save(str(self.path)))
        self.preview = ImagePreview()
        self.preview.resize(640, 480)
        self.preview.show()
        self.application.processEvents()
        self.roi = Roi(400, 300, 200, 160)
        self.assertTrue(self.preview.set_image(self.path, (self.roi,)))
        self.application.processEvents()
        self.changes: list[Roi | None] = []
        self.preview.roi_changed.connect(self.changes.append)

    def tearDown(self) -> None:
        self.preview.close()
        self.directory.cleanup()

    def wheel(self, delta: int, position: QPoint | None = None) -> None:
        position = position if position is not None else self.preview.viewport().rect().center()
        event = QWheelEvent(
            QPointF(position),
            QPointF(self.preview.viewport().mapToGlobal(position)),
            QPoint(),
            QPoint(0, delta),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(self.preview.viewport(), event)
        self.application.processEvents()

    def test_zoom_and_scroll_preserve_original_roi(self) -> None:
        scale = self.preview.transform().m11()
        bounds = self.preview.sceneRect()
        self.wheel(480)
        self.assertGreater(self.preview.transform().m11(), scale)
        self.preview.horizontalScrollBar().setValue(100)
        self.preview.verticalScrollBar().setValue(80)
        self.wheel(-120)
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_items[0].rect())
        self.assertEqual(bounds, self.preview.sceneRect())
        self.assertEqual([], self.changes)

    def test_zoom_keeps_scene_point_under_cursor(self) -> None:
        self.wheel(480)
        position = QPoint(270, 190)
        before = self.preview.mapToScene(position)
        self.wheel(120, position)
        after = self.preview.mapToScene(position)
        self.assertLess((after - before).manhattanLength(), 3 / self.preview.transform().m11())

    def test_selection_after_zoom_and_scroll_emits_original_pixels(self) -> None:
        self.wheel(600)
        self.preview.centerOn(800, 600)
        QTest.mousePress(self.preview.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(300, 240))
        QTest.mouseMove(self.preview.viewport(), QPoint(340, 260))
        QTest.mouseRelease(self.preview.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(340, 260))
        start, end = QPoint(220, 160), QPoint(400, 300)
        first, last = self.preview.mapToScene(start), self.preview.mapToScene(end)
        expected = Roi(
            math.floor(first.x()), math.floor(first.y()),
            math.ceil(last.x()) - math.floor(first.x()),
            math.ceil(last.y()) - math.floor(first.y()),
            "ui_1", "#ffb347",
        )
        QTest.mousePress(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.preview.viewport(), end)
        QTest.mouseRelease(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual([(self.roi, expected)], self.changes)
        self.assertEqual(
            QRectF(expected.x, expected.y, expected.width, expected.height),
            self.preview._roi_items[-1].rect(),
        )

    def test_resize_preserves_manual_zoom(self) -> None:
        self.wheel(360)
        scale = self.preview.transform().m11()
        self.preview.resize(800, 600)
        self.application.processEvents()
        self.assertAlmostEqual(scale, self.preview.transform().m11())
        self.assertEqual([], self.changes)

    def test_double_click_fits_image_and_preserves_roi(self) -> None:
        self.wheel(600)
        viewport = self.preview.viewport()
        position = viewport.rect().center()
        # Include the first click that precedes a native double-click event.
        QTest.mouseClick(viewport, Qt.MouseButton.LeftButton, pos=position)
        QTest.mouseDClick(viewport, Qt.MouseButton.LeftButton, pos=position)
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=position)
        self.application.processEvents()
        self.assertEqual(1.0, self.preview._zoom)
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_items[0].rect())
        self.assertEqual([], self.changes)

    def open_tag_editor(self, index=0):
        label = self.preview._labels[index]
        bounds = label.deviceTransform(self.preview.viewportTransform()).mapRect(label.boundingRect())
        QTest.mouseDClick(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=bounds.center().toPoint())
        self.application.processEvents()
        self.assertIsNotNone(self.preview._tag_editor)
        return self.preview._tag_editor

    def test_badge_double_click_edits_tag_without_changing_zoom_or_geometry(self):
        self.preview.set_rois((replace(self.roi, tag="old_tag"),))
        self.wheel(240)
        zoom = self.preview._zoom
        editor = self.open_tag_editor()
        editor.setText("new_tag")
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.assertEqual((replace(self.roi, tag="new_tag"),), self.preview.rois)
        self.assertEqual(zoom, self.preview._zoom)
        self.assertEqual([self.preview.rois], self.changes)
        self.assertIsNone(self.preview._tag_editor)

    def test_tag_editor_escape_and_invalid_names_preserve_original(self):
        rois = (replace(self.roi, tag="first"), Roi(800, 600, 100, 80, "second"))
        self.preview.set_rois(rois)
        editor = self.open_tag_editor()
        for invalid in ("", "second"):
            editor.setText(invalid)
            QTest.keyClick(editor, Qt.Key.Key_Return)
            self.assertEqual(rois, self.preview.rois)
            self.assertIsNotNone(self.preview._tag_editor)
        editor.setText("discarded")
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        self.assertIsNone(self.preview._tag_editor)
        self.assertEqual(rois, self.preview.rois)
        self.assertEqual([], self.changes)

    def test_tag_editor_focus_loss_commits_and_image_switch_cancels(self):
        self.preview.set_rois((replace(self.roi, tag="first"),))
        editor = self.open_tag_editor()
        editor.setText("committed")
        self.preview.setFocus()
        self.application.processEvents()
        self.assertEqual("committed", self.preview.rois[0].tag)
        self.open_tag_editor().setText("not_saved")
        self.preview.set_image(self.path, (self.roi,))
        self.assertIsNone(self.preview._tag_editor)
        self.assertEqual((self.roi,), self.preview.rois)

    def test_zoom_limits_and_image_change_reset(self) -> None:
        for _ in range(4):
            self.wheel(12000)
        self.assertEqual(self.preview.MAX_ZOOM, self.preview._zoom)
        for _ in range(8):
            self.wheel(-12000)
        self.assertEqual(self.preview.MIN_ZOOM, self.preview._zoom)
        self.preview.set_image(self.path, (self.roi,))
        self.assertEqual(1.0, self.preview._zoom)
        self.preview.set_image(None)
        self.assertTrue(self.preview.transform().isIdentity())

    def test_right_click_still_clears_roi_after_zoom(self) -> None:
        self.wheel(360)
        self.preview.centerOn(500, 380)
        QTest.mouseClick(self.preview.viewport(), Qt.MouseButton.RightButton,
                         pos=self.preview.mapFromScene(QPointF(500, 380)))
        self.assertEqual([], self.preview._roi_items)
        self.assertEqual([()], self.changes)

    def test_right_click_outside_preserves_rois_and_overlap_removes_only_topmost(self) -> None:
        first = Roi(400, 300, 200, 160, "user_name")
        second = Roi(450, 350, 200, 160, "password", "#ffb347")
        self.preview.set_rois((first, second))
        self.wheel(480)
        self.preview.centerOn(500, 400)
        for x, y in ((350, 250), (500, 400), (425, 325)):
            QTest.mouseClick(self.preview.viewport(), Qt.MouseButton.RightButton,
                             pos=self.preview.mapFromScene(QPointF(x, y)))
            if (x, y) == (350, 250):
                self.assertEqual((first, second), self.preview.rois)
                self.assertEqual([], self.changes)
            elif (x, y) == (500, 400):
                self.assertEqual((first,), self.preview.rois)
            else:
                self.assertEqual((), self.preview.rois)
        self.assertEqual([(first,), ()], self.changes)

    def test_repeated_drags_append_distinct_tags_and_colors(self) -> None:
        viewport = self.preview.viewport()
        for first, last in ((QPointF(100, 100), QPointF(250, 200)),
                            (QPointF(900, 600), QPointF(1100, 800))):
            start, end = self.preview.mapFromScene(first), self.preview.mapFromScene(last)
            QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(viewport, end)
            QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual(3, len(self.preview.rois))
        self.assertEqual(3, len(self.preview._roi_items))
        self.assertEqual(3, len({roi.color for roi in self.preview.rois}))
        self.assertEqual(["ui_1", "ui_2"], [r.tag for r in self.preview.rois[1:]])
        self.assertEqual(self.preview.rois, self.changes[-1])

    def drag_scene(self, start: QPointF, end: QPointF) -> None:
        viewport = self.preview.viewport()
        first, last = self.preview.mapFromScene(start), self.preview.mapFromScene(end)
        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=first)
        QTest.mouseMove(viewport, last)
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=last)

    def test_left_drag_moves_only_top_roi_after_zoom_and_preserves_metadata(self) -> None:
        from dataclasses import replace
        other = Roi(450, 350, 200, 160, "user_name", "#ffb347")
        self.preview.set_rois((self.roi, other))
        self.wheel(480)
        self.preview.centerOn(600, 450)
        first = self.preview.mapFromScene(QPointF(500, 400))
        last = first + QPoint(70, 50)
        delta = self.preview.mapToScene(last) - self.preview.mapToScene(first)
        QTest.mousePress(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=first)
        QTest.mouseMove(self.preview.viewport(), last)
        self.assertEqual([], self.changes)
        self.wheel(120)
        QTest.mouseRelease(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=last)
        expected = replace(other, x=other.x + round(delta.x()), y=other.y + round(delta.y()))
        self.assertEqual((self.roi, expected), self.preview.rois)
        self.assertEqual([(self.roi, expected)], self.changes)

    def test_move_is_clamped_to_image_without_resizing(self) -> None:
        self.drag_scene(QPointF(500, 380), QPointF(1590, 1190))
        roi = self.preview.rois[0]
        self.assertEqual((1400, 1040, 200, 160), (roi.x, roi.y, roi.width, roi.height))
        self.drag_scene(QPointF(1500, 1120), QPointF(0, 0))
        roi = self.preview.rois[0]
        self.assertEqual((0, 0, 200, 160), (roi.x, roi.y, roi.width, roi.height))

    def test_bottom_right_handle_resizes_and_limits_minimum_size_and_image_bounds(self) -> None:
        self.drag_scene(QPointF(600, 460), QPointF(1590, 1190))
        roi = self.preview.rois[0]
        self.assertEqual((400, 300), (roi.x, roi.y))
        self.assertGreater(roi.width, 1100)
        self.assertLessEqual(roi.x + roi.width, 1600)
        self.assertLessEqual(roi.y + roi.height, 1200)
        self.drag_scene(QPointF(roi.x + roi.width, roi.y + roi.height), QPointF(200, 100))
        self.assertEqual(Roi(400, 300, 2, 2), self.preview.rois[0])

    def test_handles_remain_same_screen_size_and_tags_stay_above_roi(self) -> None:
        from dataclasses import replace
        long_tag = "user_name_with_a_very_long_identifier_" * 3
        self.preview.set_rois((replace(self.roi, x=0, y=0, tag=long_tag),))
        label, handle = self.preview._labels[0], self.preview._handles[0]
        self.assertNotEqual(long_tag, label.text())
        self.assertTrue(label.text().endswith("…"))
        self.assertEqual(long_tag, label.toolTip())
        sizes = []
        for delta in (0, 480):
            if delta:
                self.wheel(delta)
            label_bounds = label.deviceTransform(self.preview.viewportTransform()).mapRect(label.boundingRect())
            roi_top = self.preview.mapFromScene(QPointF(0, 0)).y()
            self.assertLess(label_bounds.bottom(), roi_top)
            if not delta:
                self.assertGreaterEqual(label_bounds.top(), 0)
            sizes.append(handle.deviceTransform(self.preview.viewportTransform()).mapRect(handle.rect()).size())
        self.assertEqual(sizes[0], sizes[1])

    def test_escape_or_focus_loss_cancels_roi_edit_without_emitting_change(self) -> None:
        for cancel in (lambda: QTest.keyClick(self.preview, Qt.Key.Key_Escape),
                       lambda: QApplication.sendEvent(self.preview, QFocusEvent(QEvent.Type.FocusOut))):
            start = self.preview.mapFromScene(QPointF(500, 380))
            end = start + QPoint(40, 20)
            QTest.mousePress(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(self.preview.viewport(), end)
            self.assertNotEqual((self.roi,), self.preview.rois)
            cancel()
            QTest.mouseRelease(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=end)
            self.assertEqual((self.roi,), self.preview.rois)
            self.assertEqual([], self.changes)

    def test_middle_drag_pans_without_changing_zoom_or_roi(self) -> None:
        self.wheel(600)
        self.preview.centerOn(800, 600)
        viewport = self.preview.viewport()
        start, end = QPoint(300, 240), QPoint(360, 280)
        horizontal = self.preview.horizontalScrollBar().value()
        vertical = self.preview.verticalScrollBar().value()
        transform = self.preview.transform()
        QTest.mousePress(viewport, Qt.MouseButton.MiddleButton, pos=start)
        self.assertEqual(Qt.CursorShape.ClosedHandCursor, viewport.cursor().shape())
        QTest.mouseMove(viewport, end)
        self.wheel(120)
        QTest.mouseRelease(viewport, Qt.MouseButton.MiddleButton, pos=end)
        self.assertEqual(horizontal - 60, self.preview.horizontalScrollBar().value())
        self.assertEqual(vertical - 40, self.preview.verticalScrollBar().value())
        self.assertEqual(transform, self.preview.transform())
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_items[0].rect())
        self.assertEqual([], self.changes)
        self.assertIsNone(self.preview._pan_origin)
        self.assertNotEqual(Qt.CursorShape.ClosedHandCursor, viewport.cursor().shape())
        horizontal = self.preview.horizontalScrollBar().value()
        QTest.mouseMove(viewport, QPoint(390, 290))
        self.assertEqual(horizontal, self.preview.horizontalScrollBar().value())

    def test_image_change_and_focus_loss_stop_middle_drag(self) -> None:
        viewport = self.preview.viewport()
        for reset in (
            lambda: self.preview.set_image(self.path, (self.roi,)),
            lambda: QApplication.sendEvent(self.preview, QFocusEvent(QEvent.Type.FocusOut)),
        ):
            with self.subTest(reset=reset):
                QTest.mousePress(viewport, Qt.MouseButton.MiddleButton, pos=QPoint(300, 240))
                self.assertIsNotNone(self.preview._pan_origin)
                reset()
                self.assertIsNone(self.preview._pan_origin)
                self.assertNotEqual(Qt.CursorShape.ClosedHandCursor, viewport.cursor().shape())
                QTest.mouseRelease(viewport, Qt.MouseButton.MiddleButton, pos=QPoint(300, 240))
        self.preview.set_image(None)
        QTest.mouseClick(viewport, Qt.MouseButton.MiddleButton)
        self.assertIsNone(self.preview._pan_origin)
        self.assertEqual([], self.changes)


if __name__ == "__main__":
    unittest.main()
