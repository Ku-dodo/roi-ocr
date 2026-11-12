from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsItem,
    QGraphicsSimpleTextItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from ocr_app.domain.models import Roi


class ImagePreview(QGraphicsView):
    roi_changed = Signal(object)
    MIN_ZOOM = 0.1
    MAX_ZOOM = 20.0
    ROI_COLORS = ("#45a3ff", "#ffb347", "#72d98b", "#d58bff", "#ff7272", "#55d6d0", "#ff82be", "#c7d94a")

    def __init__(self) -> None:
        super().__init__()
        self._graphics_scene = QGraphicsScene(self)
        self.setScene(self._graphics_scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._roi_item: QGraphicsRectItem | None = None
        self._drag_origin: QPointF | None = None
        self._rois: tuple[Roi, ...] = ()
        self._roi_items: list[QGraphicsRectItem] = []
        self._pan_origin: QPoint | None = None
        self._zoom = 1.0

        self.setBackgroundBrush(QColor("#111315"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setToolTip(
            "왼쪽 드래그로 모든 이미지에 적용할 ROI를 추가합니다. 아래 표에서 Tag / UI ID를 편집할 수 있습니다. "
            "휠로 확대·축소하고 더블클릭하면 전체 이미지에 맞춥니다. "
            "휠 버튼을 누른 채 드래그하면 이미지를 이동합니다. "
            "ROI 내부를 오른쪽 클릭하면 해당 ROI가 해제됩니다."
        )

    def set_image(self, path: Path | None, rois: tuple[Roi, ...] = ()) -> bool:
        self._stop_panning()
        self._graphics_scene.clear()
        self._pixmap_item = None
        self._roi_item = None
        self._drag_origin = None
        self._rois = ()
        self._roi_items = []
        self._zoom = 1.0
        self.resetTransform()

        if path is None:
            self._show_message("파일을 선택하면 이미지가 표시됩니다.")
            return False

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._show_message("이미지를 표시할 수 없습니다.")
            return False

        self._pixmap_item = self._graphics_scene.addPixmap(pixmap)
        self._graphics_scene.setSceneRect(QRectF(pixmap.rect()))
        self.set_rois(rois)
        self._fit_image()
        return True

    @property
    def rois(self) -> tuple[Roi, ...]:
        return self._rois

    def set_rois(self, rois: tuple[Roi, ...]) -> None:
        self._discard_draft()
        for item in self._roi_items:
            self._graphics_scene.removeItem(item)
        self._roi_items = []
        self._rois = tuple(rois)
        if self._pixmap_item is None:
            return
        for roi in self._rois:
            color = QColor(roi.color)
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            item = self._graphics_scene.addRect(QRectF(roi.x, roi.y, roi.width, roi.height), pen)
            fill = QColor(color)
            fill.setAlpha(35)
            item.setBrush(fill)
            item.setZValue(10)
            label = QGraphicsSimpleTextItem(roi.tag, item)
            label.setBrush(color)
            label.setPos(roi.x + 3, roi.y + 2)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            self._roi_items.append(item)

    def _discard_draft(self) -> None:
        self._drag_origin = None
        if self._roi_item is not None:
            self._graphics_scene.removeItem(self._roi_item)
            self._roi_item = None

    def clear_roi(self) -> None:
        self.set_rois(())
        self.roi_changed.emit(())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._zoom == 1.0:
            self._fit_image()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            super().wheelEvent(event)
            return

        # Keep an in-progress selection in the same view until it is committed.
        if self._drag_origin is not None or self._pan_origin is not None:
            event.accept()
            return

        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            steps = max(-10.0, min(10.0, delta / 120.0))
            zoom = max(self.MIN_ZOOM, min(self._zoom * 1.2 ** steps, self.MAX_ZOOM))
            position = event.position().toPoint()
            before = self.mapToScene(position)
            self.scale(zoom / self._zoom, zoom / self._zoom)
            self._zoom = zoom
            after = self.mapToScene(position)
            # Only the view transform changes; scene coordinates remain image pixels.
            offset = after - before
            self.translate(offset.x(), offset.y())
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._pan_origin is not None:
            event.accept()
            return
        if self._pixmap_item is not None and event.button() == Qt.MouseButton.LeftButton:
            self._discard_draft()
            self._fit_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._pixmap_item is None:
            super().mousePressEvent(event)
            return

        if self._pan_origin is not None:
            event.accept()
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            if self._drag_origin is None:
                self._pan_origin = event.position().toPoint()
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            point = self.mapToScene(event.position().toPoint())
            for index in range(len(self._rois) - 1, -1, -1):
                roi = self._rois[index]
                if QRectF(roi.x, roi.y, roi.width, roi.height).contains(point):
                    self.set_rois(self._rois[:index] + self._rois[index + 1:])
                    self.roi_changed.emit(self._rois)
                    break
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = self._clamped_scene_point(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_origin is not None:
            position = event.position().toPoint()
            delta = position - self._pan_origin
            self._pan_origin = position
            horizontal = self.horizontalScrollBar()
            vertical = self.verticalScrollBar()
            horizontal.setValue(horizontal.value() - delta.x())
            vertical.setValue(vertical.value() - delta.y())
            event.accept()
            return
        if self._drag_origin is not None:
            current = self._clamped_scene_point(event.position().toPoint())
            self._set_roi_rect(QRectF(self._drag_origin, current).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_origin is not None:
            if event.button() == Qt.MouseButton.MiddleButton:
                self._stop_panning()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            current = self._clamped_scene_point(event.position().toPoint())
            rectangle = QRectF(self._drag_origin, current).normalized()
            self._drag_origin = None

            left = math.floor(rectangle.left())
            top = math.floor(rectangle.top())
            right = math.ceil(rectangle.right())
            bottom = math.ceil(rectangle.bottom())
            self._discard_draft()
            if right - left >= 2 and bottom - top >= 2:
                number = 1
                tags = {roi.tag for roi in self._rois}
                while f"ui_{number}" in tags:
                    number += 1
                used_colors = {roi.color for roi in self._rois}
                color = next((c for c in self.ROI_COLORS if c not in used_colors),
                             self.ROI_COLORS[len(self._rois) % len(self.ROI_COLORS)])
                roi = Roi(left, top, right - left, bottom - top, f"ui_{number}", color)
                self.set_rois(self._rois + (roi,))
                self.roi_changed.emit(self._rois)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._stop_panning()
        super().focusOutEvent(event)

    def _stop_panning(self) -> None:
        if self._pan_origin is not None:
            self._pan_origin = None
            self.viewport().unsetCursor()

    def _fit_image(self) -> None:
        if self._pixmap_item is not None:
            self._zoom = 1.0
            self.fitInView(self._graphics_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _clamped_scene_point(self, viewport_point) -> QPointF:
        point = self.mapToScene(viewport_point)
        bounds = self._graphics_scene.sceneRect()
        return QPointF(
            max(bounds.left(), min(point.x(), bounds.right())),
            max(bounds.top(), min(point.y(), bounds.bottom())),
        )

    def _set_roi_rect(self, rectangle: QRectF) -> None:
        if self._roi_item is None:
            pen = QPen(QColor("#45a3ff"), 2)
            pen.setCosmetic(True)
            self._roi_item = self._graphics_scene.addRect(rectangle, pen)
            self._roi_item.setBrush(QColor(69, 163, 255, 35))
            self._roi_item.setZValue(10)
        else:
            self._roi_item.setRect(rectangle)

    def _show_message(self, message: str) -> None:
        text_item = self._graphics_scene.addText(message)
        text_item.setDefaultTextColor(QColor("#9da3aa"))
        self._graphics_scene.setSceneRect(text_item.boundingRect().adjusted(-20, -20, 20, 20))
