from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGraphicsView, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QVBoxLayout,
)

from ocr_app.domain.models import Roi
from ocr_app.presentation.image_preview import ImagePreview


class _DraftPreview(ImagePreview):
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            super().mousePressEvent(event)
        else:
            QGraphicsView.mousePressEvent(self, event)


class RoiDraftDialog(QDialog):
    def __init__(self, path: Path, existing: tuple[Roi, ...], candidates: tuple[Roi, ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI 자동 찾기 · 후보 검토")
        self.resize(1100, 700)
        self._existing, self._candidates = existing, candidates
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "추가할 후보를 체크하세요. 기존 ROI는 유지되며, 현재 이미지에만 추가됩니다.\n"
            "적용 후 이동·크기 조절·삭제·Tag 편집을 하고 프리셋으로 저장할 수 있습니다."
        ))
        row = QHBoxLayout()
        self._preview = _DraftPreview()
        self._preview.setToolTip("휠: 확대·축소 / 휠 버튼 드래그: 화면 이동\n후보 선택은 왼쪽 목록에서 합니다.")
        self._preview.set_image(path)
        self._list = QListWidget()
        self._list.setMaximumWidth(300)
        for roi in candidates:
            item = QListWidgetItem(f"{roi.tag}   ({roi.x}, {roi.y}, {roi.width}, {roi.height})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._list.addItem(item)
        row.addWidget(self._list)
        row.addWidget(self._preview, 1)
        layout.addLayout(row, 1)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("선택 후보 추가")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._list.itemChanged.connect(self._refresh)
        self._refresh()

    def selected_rois(self) -> tuple[Roi, ...]:
        return tuple(roi for index, roi in enumerate(self._candidates)
                     if self._list.item(index).checkState() == Qt.CheckState.Checked)

    def _refresh(self, *_args) -> None:
        selected = self.selected_rois()
        self._preview.set_rois(self._existing + selected)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(selected))
