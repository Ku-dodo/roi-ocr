from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QMouseEvent, QPainter, QPen, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsItem,
    QGraphicsSimpleTextItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QToolTip,
)

from ocr_app.domain.models import ROI_COLORS, Roi, next_roi_color
from ocr_app.presentation.roi_graphics import RoiOutline, RoiTagBadge


class ImagePreview(QGraphicsView):
    roi_changed = Signal(object)
    tag_renamed = Signal(str, str)
    MIN_ZOOM = 0.1
    MAX_ZOOM = 20.0
    HANDLE_SIZE = 10
    TAG_MAX_WIDTH = 160
    ROI_COLORS = ROI_COLORS
    TAG_EDITABLE = True

    def __init__(self) -> None:
        super().__init__()
        self._graphics_scene = QGraphicsScene(self)
        self.setScene(self._graphics_scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._roi_item: QGraphicsRectItem | None = None
        self._drag_origin: QPointF | None = None
        self._rois: tuple[Roi, ...] = ()
        self._roi_items: list[QGraphicsRectItem] = []
        self._handles: list[QGraphicsRectItem] = []
        self._labels: list[QGraphicsSimpleTextItem] = []
        self._edit_index: int | None = None
        self._edit_before: Roi | None = None
        self._edit_origin = QPointF()
        self._edit_mode = ""
        self._pan_origin: QPoint | None = None
        self._zoom = 1.0
        self._tag_editor: QLineEdit | None = None
        self._tag_edit_index: int | None = None

        self.setBackgroundBrush(QColor("#111315"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setToolTip(
            "ROI 추가: 빈 곳에서 왼쪽 드래그\n"
            "ROI 이동: 영역 안에서 드래그\n"
            "크기 조절: 오른쪽 아래 핸들 드래그\n"
            "ROI 삭제: 영역 안에서 오른쪽 클릭\n"
            "확대·축소: 휠 / 전체 보기: 더블클릭\n"
            "화면 이동: 휠 버튼을 누른 채 드래그\n"
            "Tag 편집: 상단 배지 더블클릭"
        )

    def set_image(self, path: Path | None, rois: tuple[Roi, ...] = ()) -> bool:
        """진행 중인 편집·이동을 취소하고 새 이미지와 ROI로 장면을 교체한다.

        Args:
            path: 이미지 경로. None이면 선택 안내를 표시한다.
            rois: 원본 픽셀 좌표로 표시할 ROI 튜플.

        Returns:
            이미지를 표시했으면 True, 경로가 없거나 읽지 못했으면 False.
            확대 상태를 초기화하고 새 이미지를 화면에 맞춘다.
        """
        self._stop_panning()
        self._cancel_tag_edit()
        self._cancel_roi_edit()
        self._graphics_scene.clear()
        self._pixmap_item = None
        self._roi_item = None
        self._drag_origin = None
        self._rois = ()
        self._roi_items = []
        self._handles = []
        self._labels = []
        self._zoom = 1.0
        self.resetTransform()
        self.setSceneRect(QRectF())

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
        self._cancel_tag_edit()
        self._cancel_roi_edit()
        self._discard_draft()
        for label in self._labels:
            self._graphics_scene.removeItem(label)
        for item in self._roi_items:
            self._graphics_scene.removeItem(item)
        self._roi_items = []
        self._handles = []
        self._labels = []
        self._rois = tuple(rois)
        if self._pixmap_item is None:
            return
        for roi in self._rois:
            color = QColor(roi.color)
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            item = RoiOutline(QRectF(roi.x, roi.y, roi.width, roi.height))
            item.setPen(pen)
            self._graphics_scene.addItem(item)
            item.setZValue(10)
            label = RoiTagBadge(color, None)
            self._graphics_scene.addItem(label)
            label.setZValue(30)
            label.setText(QFontMetricsF(label.font()).elidedText(roi.tag, Qt.TextElideMode.ElideRight, self.TAG_MAX_WIDTH))
            label.setToolTip(roi.tag)
            label.setPos(roi.x, roi.y)
            label.setTransform(QTransform.fromTranslate(0, -label.boundingRect().height() - 4))
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            handle = QGraphicsRectItem(QRectF(-self.HANDLE_SIZE / 2, -self.HANDLE_SIZE / 2,
                                              self.HANDLE_SIZE, self.HANDLE_SIZE), item)
            handle.setPos(roi.x + roi.width, roi.y + roi.height)
            handle.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            handle.setBrush(color)
            handle.setPen(QPen(QColor("#111315"), 1))
            handle.setToolTip("드래그하여 ROI 크기 조절")
            self._roi_items.append(item)
            self._handles.append(handle)
            self._labels.append(label)

    def _hit_roi(self, position: QPoint) -> tuple[int | None, str]:
        """화면 좌표에서 가장 위의 ROI와 가능한 편집 동작을 찾는다.

        Args:
            position: 뷰포트의 마우스 좌표. 핸들 판정은 확대율과 무관한 화면 크기를 쓴다.

        Returns:
            (ROI 인덱스, 동작). 핸들은 resize, 내부는 move이며 없으면 (None, "").
        """
        point = self.mapToScene(position)
        for index in range(len(self._rois) - 1, -1, -1):
            roi = self._rois[index]
            handle = self._handles[index]
            handle_rect = handle.deviceTransform(self.viewportTransform()).mapRect(handle.rect())
            if handle_rect.contains(QPointF(position)):
                return index, "resize"
            if QRectF(roi.x, roi.y, roi.width, roi.height).contains(point):
                return index, "move"
        return None, ""

    def _hit_tag(self, position: QPoint) -> int | None:
        """뷰포트 좌표를 받아 확대율과 무관한 Tag 배지의 최상단 인덱스를 반환한다."""
        for index in range(len(self._labels) - 1, -1, -1):
            label = self._labels[index]
            bounds = label.deviceTransform(self.viewportTransform()).mapRect(label.boundingRect())
            if bounds.contains(QPointF(position)):
                return index
        return None

    def _start_tag_edit(self, index: int) -> None:
        """ROI 인덱스를 받아 배지 위치에 원문 Tag 편집기를 띄운다. 반환값은 없다."""
        self._cancel_tag_edit()
        self._cancel_roi_edit()
        self._discard_draft()
        label = self._labels[index]
        bounds = label.deviceTransform(self.viewportTransform()).mapRect(label.boundingRect())
        editor = QLineEdit(self.viewport())
        editor.setText(self._rois[index].tag)
        editor.setStyleSheet("QLineEdit { background: #17212f; color: white; border: 2px solid #69b7ff; padding: 3px; }")
        width = min(360, max(180, int(bounds.width()) + 20), self.viewport().width())
        x = max(0, min(int(bounds.x()), self.viewport().width() - width))
        y = max(0, min(int(bounds.y()), self.viewport().height() - 32))
        editor.setGeometry(x, y, width, 32)
        self._tag_editor, self._tag_edit_index = editor, index
        editor.installEventFilter(self)
        editor.returnPressed.connect(self._commit_tag_edit)
        editor.editingFinished.connect(self._commit_tag_edit)
        editor.show()
        editor.setFocus()
        editor.selectAll()

    def _cancel_tag_edit(self) -> None:
        if self._tag_editor is not None:
            editor = self._tag_editor
            self._tag_editor, self._tag_edit_index = None, None
            editor.blockSignals(True)
            editor.hide()
            editor.deleteLater()

    def _commit_tag_edit(self) -> None:
        """입력된 Tag를 검증해 ROI 표와 공유한다. 빈 값·중복은 저장하지 않는다.

        Returns:
            None. 유효한 변경은 roi_changed로 전달한다. 잘못된 입력은 안내하며,
            포커스가 떠났다면 기존 Tag를 유지하고 편집기를 닫는다.
        """
        editor, index = self._tag_editor, self._tag_edit_index
        if editor is None or index is None:
            return
        tag = editor.text().strip()
        if not tag or any(roi.tag == tag for i, roi in enumerate(self._rois) if i != index):
            QToolTip.showText(editor.mapToGlobal(QPoint(0, editor.height())), "Tag는 비어 있거나 중복될 수 없습니다.", editor)
            editor.setStyleSheet("QLineEdit { background: #17212f; color: white; border: 2px solid #ff7272; padding: 3px; }")
            if not editor.hasFocus():
                self._cancel_tag_edit()
            return
        old_tag = self._rois[index].tag
        changed = tag != old_tag
        rois = list(self._rois)
        rois[index] = replace(rois[index], tag=tag)
        self._cancel_tag_edit()
        if changed:
            self.tag_renamed.emit(old_tag, tag)
            self.set_rois(tuple(rois))
            self.roi_changed.emit(self._rois)

    def eventFilter(self, watched, event) -> bool:
        if watched is self._tag_editor and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self._cancel_tag_edit()
            return True
        return super().eventFilter(watched, event)

    def _update_roi_graphics(self, index: int) -> None:
        roi = self._rois[index]
        self._roi_items[index].setRect(QRectF(roi.x, roi.y, roi.width, roi.height))
        self._handles[index].setPos(roi.x + roi.width, roi.y + roi.height)
        self._labels[index].setPos(roi.x, roi.y)

    def _drag_roi(self, position: QPoint) -> None:
        """편집 시작 시점의 영역과 마우스 이동량으로 위치 또는 크기를 계산한다.

        Args:
            position: 현재 마우스의 뷰포트 좌표. 원본 이미지 좌표로 변환한다.

        Returns:
            None. 영역을 이미지 경계 안으로 제한하여 즉시 표시하며,
            확정 신호는 여기서 보내지 않고 마우스를 놓을 때 보낸다.
        """
        if self._edit_index is None or self._edit_before is None:
            return
        delta = self.mapToScene(position) - self._edit_origin
        roi = self._edit_before
        bounds = self._pixmap_item.boundingRect()
        if self._edit_mode == "move":
            updated = replace(roi,
                x=max(0, min(roi.x + round(delta.x()), max(0, int(bounds.width()) - roi.width))),
                y=max(0, min(roi.y + round(delta.y()), max(0, int(bounds.height()) - roi.height))))
        else:
            updated = replace(roi,
                width=max(2, min(roi.width + round(delta.x()), int(bounds.right()) - roi.x)),
                height=max(2, min(roi.height + round(delta.y()), int(bounds.bottom()) - roi.y)))
        rois = list(self._rois)
        rois[self._edit_index] = updated
        self._rois = tuple(rois)
        self._update_roi_graphics(self._edit_index)

    def _cancel_roi_edit(self) -> None:
        """입력 인자 없이 현재 이동·크기 조절을 시작 전 좌표로 되돌린다.

        Returns:
            None. 편집 상태와 커서를 초기화하며 roi_changed 신호는 보내지 않는다.
        """
        if self._edit_index is not None and self._edit_before is not None:
            rois = list(self._rois)
            rois[self._edit_index] = self._edit_before
            self._rois = tuple(rois)
            self._update_roi_graphics(self._edit_index)
        self._edit_index = None
        self._edit_before = None
        self.viewport().unsetCursor()

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
        """커서 아래의 이미지 지점을 유지하면서 뷰만 확대·축소한다.

        Args:
            event: Qt 휠 이벤트. 드래그·화면 이동·ROI 편집 중에는 확대를 무시한다.

        Returns:
            None. ROI의 원본 픽셀 좌표는 변경하지 않는다.
        """
        if self._tag_editor is not None:
            event.accept()
            return
        if self._pixmap_item is None:
            super().wheelEvent(event)
            return

        # Keep an in-progress selection in the same view until it is committed.
        if self._drag_origin is not None or self._pan_origin is not None or self._edit_index is not None:
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
            index = self._hit_tag(event.position().toPoint())
            if index is not None:
                if self.TAG_EDITABLE:
                    self._start_tag_edit(index)
                event.accept()
                return
            self._cancel_roi_edit()
            self._discard_draft()
            self._fit_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """마우스 위치와 버튼에 따라 ROI 편집 또는 화면 이동을 시작한다.

        Args:
            event: Qt 마우스 누름 이벤트. 왼쪽은 영역 추가·이동·크기 조절,
                가운데는 화면 이동, 오른쪽은 가장 위의 ROI 하나 삭제에 사용한다.

        Returns:
            None. 편집 중 오른쪽 클릭은 삭제 대신 현재 편집을 취소한다.
        """
        if self._pixmap_item is None:
            super().mousePressEvent(event)
            return

        if self._pan_origin is not None:
            event.accept()
            return

        if self._edit_index is not None:
            if event.button() == Qt.MouseButton.RightButton:
                self._cancel_roi_edit()
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
            if self._hit_tag(event.position().toPoint()) is not None:
                event.accept()
                return
            index, mode = self._hit_roi(event.position().toPoint())
            if index is not None:
                self._edit_index = index
                self._edit_before = self._rois[index]
                self._edit_origin = self.mapToScene(event.position().toPoint())
                self._edit_mode = mode
                self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor if mode == "resize" else Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
            self._drag_origin = self._clamped_scene_point(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._edit_index is not None:
            self._drag_roi(event.position().toPoint())
            event.accept()
            return
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
        if self._pixmap_item is not None:
            index, mode = self._hit_roi(event.position().toPoint())
            self.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor if mode == "resize" else (
                Qt.CursorShape.OpenHandCursor if index is not None else Qt.CursorShape.ArrowCursor))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """드래그를 확정하고 실제로 변경된 ROI를 외부에 알린다.

        Args:
            event: Qt 마우스 놓음 이벤트. 시작한 드래그와 같은 버튼만 확정한다.

        Returns:
            None. 새 영역은 좌표를 바깥 정수로 반올림하고 최소 크기를 검사한다.
            유효한 새 영역 또는 변경된 편집 결과를 roi_changed 신호로 전달한다.
        """
        if self._edit_index is not None:
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_roi(event.position().toPoint())
                changed = self._rois[self._edit_index] != self._edit_before
                self._edit_index = None
                self._edit_before = None
                self.viewport().unsetCursor()
                if changed:
                    self.roi_changed.emit(self._rois)
            event.accept()
            return
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
                color = next_roi_color(self._rois)
                roi = Roi(left, top, right - left, bottom - top, f"ui_{number}", color)
                self.set_rois(self._rois + (roi,))
                self.roi_changed.emit(self._rois)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._stop_panning()
        self._cancel_roi_edit()
        super().focusOutEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._stop_panning()
            self._cancel_roi_edit()
            self._discard_draft()
            event.accept()
            return
        super().keyPressEvent(event)

    def _stop_panning(self) -> None:
        if self._pan_origin is not None:
            self._pan_origin = None
            self.viewport().unsetCursor()

    def _fit_image(self) -> None:
        if self._pixmap_item is not None:
            self._zoom = 1.0
            bounds = self._pixmap_item.boundingRect()
            scale = min(self.viewport().width() / bounds.width(), self.viewport().height() / bounds.height())
            padding = 32 / max(scale, 0.001)
            view_bounds = bounds.adjusted(-padding, -padding, padding, padding)
            self.setSceneRect(view_bounds)
            self.fitInView(view_bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def _clamped_scene_point(self, viewport_point) -> QPointF:
        """뷰포트 좌표를 원본 이미지 좌표로 바꾸고 이미지 경계 안으로 제한한다.

        Args:
            viewport_point: 마우스 등에서 얻은 뷰포트 좌표. 이미지가 로드되어 있어야 한다.

        Returns:
            원본 이미지 범위 안의 장면 좌표 QPointF.
        """
        point = self.mapToScene(viewport_point)
        bounds = self._pixmap_item.boundingRect()
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
