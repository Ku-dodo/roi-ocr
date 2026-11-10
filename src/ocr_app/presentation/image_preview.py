from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from ocr_app.domain.models import Roi


class ImagePreview(QGraphicsView):
    roi_changed = Signal(object)
    MIN_ZOOM = 0.1
    MAX_ZOOM = 20.0

    def __init__(self) -> None:
        super().__init__()
        self._graphics_scene = QGraphicsScene(self)
        self.setScene(self._graphics_scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._roi_item: QGraphicsRectItem | None = None
        self._drag_origin: QPointF | None = None
        self._roi_before_drag: QRectF | None = None
        self._zoom = 1.0

        self.setBackgroundBrush(QColor("#111315"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setToolTip(
            "마우스로 드래그하여 모든 이미지에 적용할 Static ROI를 지정합니다. "
            "휠로 확대·축소하고 더블클릭하면 전체 이미지에 맞춥니다. "
            "오른쪽 클릭하면 Static ROI가 해제됩니다."
        )

    def set_image(self, path: Path | None, roi: Roi | None = None) -> bool:
        self._graphics_scene.clear()
        self._pixmap_item = None
        self._roi_item = None
        self._drag_origin = None
        self._roi_before_drag = None
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
        if roi is not None:
            self._set_roi_rect(QRectF(roi.x, roi.y, roi.width, roi.height))
        self._fit_image()
        return True

    def clear_roi(self) -> None:
        self._drag_origin = None
        self._roi_before_drag = None
        if self._roi_item is not None:
            self._graphics_scene.removeItem(self._roi_item)
            self._roi_item = None
        self.roi_changed.emit(None)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._zoom == 1.0:
            self._fit_image()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            super().wheelEvent(event)
            return

        # Keep an in-progress selection in the same view until it is committed.
        if self._drag_origin is not None:
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
        if self._pixmap_item is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = None
            self._fit_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._pixmap_item is None:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.clear_roi()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._roi_before_drag = (
                QRectF(self._roi_item.rect()) if self._roi_item is not None else None
            )
            self._drag_origin = self._clamped_scene_point(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is not None:
            current = self._clamped_scene_point(event.position().toPoint())
            self._set_roi_rect(QRectF(self._drag_origin, current).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            current = self._clamped_scene_point(event.position().toPoint())
            rectangle = QRectF(self._drag_origin, current).normalized()
            self._drag_origin = None

            left = math.floor(rectangle.left())
            top = math.floor(rectangle.top())
            right = math.ceil(rectangle.right())
            bottom = math.ceil(rectangle.bottom())
            if right - left >= 2 and bottom - top >= 2:
                roi = Roi(left, top, right - left, bottom - top)
                self._set_roi_rect(QRectF(roi.x, roi.y, roi.width, roi.height))
                self.roi_changed.emit(roi)
            elif self._roi_before_drag is not None:
                self._set_roi_rect(self._roi_before_drag)
            else:
                self.clear_roi()
            self._roi_before_drag = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
