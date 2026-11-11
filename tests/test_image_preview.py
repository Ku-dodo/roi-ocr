from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest
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
        self.assertTrue(self.preview.set_image(self.path, self.roi))
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
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_item.rect())
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
        )
        QTest.mousePress(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(self.preview.viewport(), end)
        QTest.mouseRelease(self.preview.viewport(), Qt.MouseButton.LeftButton, pos=end)
        self.assertEqual([expected], self.changes)
        self.assertEqual(
            QRectF(expected.x, expected.y, expected.width, expected.height),
            self.preview._roi_item.rect(),
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
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_item.rect())
        self.assertEqual([], self.changes)

    def test_zoom_limits_and_image_change_reset(self) -> None:
        for _ in range(4):
            self.wheel(12000)
        self.assertEqual(self.preview.MAX_ZOOM, self.preview._zoom)
        for _ in range(8):
            self.wheel(-12000)
        self.assertEqual(self.preview.MIN_ZOOM, self.preview._zoom)
        self.preview.set_image(self.path, self.roi)
        self.assertEqual(1.0, self.preview._zoom)
        self.preview.set_image(None)
        self.assertTrue(self.preview.transform().isIdentity())

    def test_right_click_still_clears_roi_after_zoom(self) -> None:
        self.wheel(360)
        QTest.mouseClick(self.preview.viewport(), Qt.MouseButton.RightButton)
        self.assertIsNone(self.preview._roi_item)
        self.assertEqual([None], self.changes)

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
        self.assertEqual(QRectF(400, 300, 200, 160), self.preview._roi_item.rect())
        self.assertEqual([], self.changes)
        self.assertIsNone(self.preview._pan_origin)
        self.assertNotEqual(Qt.CursorShape.ClosedHandCursor, viewport.cursor().shape())
        horizontal = self.preview.horizontalScrollBar().value()
        QTest.mouseMove(viewport, QPoint(390, 290))
        self.assertEqual(horizontal, self.preview.horizontalScrollBar().value())

    def test_image_change_and_focus_loss_stop_middle_drag(self) -> None:
        viewport = self.preview.viewport()
        for reset in (
            lambda: self.preview.set_image(self.path, self.roi),
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
