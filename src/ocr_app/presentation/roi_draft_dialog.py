from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGraphicsView, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QVBoxLayout,
)

from ocr_app.domain.models import Roi
from ocr_app.presentation.image_preview import ImagePreview


class _DraftPreview(ImagePreview):
    TAG_EDITABLE = False
    candidate_excluded = Signal(str)

    def mousePressEvent(self, event) -> None:
        """후보를 우클릭하면 제외 요청을 보내고 가운데 버튼은 화면 이동에 사용한다.

        Args:
            event: Qt 마우스 누름 이벤트. 우클릭한 영역은 Tag로 알린다.

        Returns:
            None. 후보 제외는 신호를 받은 대화상자가 체크 해제로 처리한다.
            왼쪽 버튼은 기본 뷰에 전달하여 영역 추가·이동을 시작하지 않는다.
        """
        if event.button() == Qt.MouseButton.RightButton:
            if self._pan_origin is None:
                index, _ = self._hit_roi(event.position().toPoint())
                if index is not None:
                    self.candidate_excluded.emit(self._rois[index].tag)
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            super().mousePressEvent(event)
        else:
            QGraphicsView.mousePressEvent(self, event)


class RoiDraftDialog(QDialog):
    def __init__(self, path: Path, existing: tuple[Roi, ...], candidates: tuple[Roi, ...], parent=None):
        """후보 선택 목록과 원본 이미지 미리보기가 있는 검토 창을 구성한다.

        Args:
            path: 미리보기에 표시할 이미지 파일 경로.
            existing: 미리보기에 함께 표시할 기존 ROI. 이 창에서 변경하지 않는다.
            candidates: 추가 여부를 선택할 자동 검출 후보 튜플.
            parent: 대화상자의 부모 Qt 위젯. 없으면 독립 창으로 생성한다.

        Returns:
            None. 후보를 모두 선택한 상태로 생성하며, 창 표시는 호출자가 수행한다.
        """
        super().__init__(parent)
        self.setWindowTitle("ROI 자동 찾기 · 후보 검토")
        self.resize(1100, 700)
        self._existing, self._candidates = existing, candidates
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "추가할 후보를 체크하세요. 영역 우클릭으로 제외하고 목록에서 다시 선택할 수 있습니다.\n"
            "기존 ROI는 유지되며, 선택 후보는 현재 이미지에만 추가됩니다.\n"
            "적용 후 이동·크기 조절·삭제·Tag 편집을 하고 프리셋으로 저장할 수 있습니다."
        ))
        row = QHBoxLayout()
        self._preview = _DraftPreview()
        self._preview.setToolTip("우클릭: 후보 제외 / 목록 체크: 다시 포함\n휠: 확대·축소 / 휠 버튼 드래그: 화면 이동")
        self._preview.set_image(path)
        self._list = QListWidget()
        self._list.setMaximumWidth(300)
        for roi in candidates:
            item = QListWidgetItem(f"{roi.tag}   ({roi.x}, {roi.y}, {roi.width}, {roi.height})")
            swatch = QPixmap(14, 14)
            swatch.fill(QColor(roi.color))
            item.setIcon(QIcon(swatch))
            item.setToolTip(f"{roi.tag} · 색상 {roi.color}\n체크를 해제하면 제외되며 다시 체크하면 복원됩니다.")
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
        self._preview.candidate_excluded.connect(self._exclude_candidate)
        self._refresh()

    def selected_rois(self) -> tuple[Roi, ...]:
        """입력 인자 없이 목록의 체크 상태를 읽어 선택된 후보만 반환한다.

        Returns:
            원래 후보 순서를 유지한 ROI 튜플. 모두 해제했으면 빈 튜플이다.
            기존 ROI는 이 반환값에 포함하지 않는다.
        """
        return tuple(roi for index, roi in enumerate(self._candidates)
                     if self._list.item(index).checkState() == Qt.CheckState.Checked)

    def _refresh(self, *_args) -> None:
        """체크 상태에 맞춰 미리보기와 후보 추가 버튼을 갱신한다.

        Args:
            *_args: Qt itemChanged 신호가 전달하는 인자. 내용은 사용하지 않는다.

        Returns:
            None. 제외한 후보는 회색 목록 항목으로 남기고 미리보기에서는 숨긴다.
            기존 ROI와 선택 후보를 표시하고 선택이 없으면 추가 버튼을 끈다.
        """
        self._list.blockSignals(True)
        for index in range(self._list.count()):
            item = self._list.item(index)
            checked = item.checkState() == Qt.CheckState.Checked
            group = QPalette.ColorGroup.Active if checked else QPalette.ColorGroup.Disabled
            item.setForeground(self._list.palette().color(group, QPalette.ColorRole.Text))
            if not checked:
                item.setSelected(False)
        self._list.blockSignals(False)
        selected = self.selected_rois()
        self._preview.set_rois(self._existing + selected)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(selected))

    def _exclude_candidate(self, tag: str) -> None:
        """우클릭한 자동 후보의 체크만 해제하며 원래 ROI와 목록 항목은 보존한다.

        Args:
            tag: 미리보기에서 우클릭한 ROI의 Tag. 기존 수동 ROI이면 무시한다.

        Returns:
            None. 체크 변경 신호가 미리보기와 추가 버튼 상태를 함께 갱신한다.
        """
        for index, roi in enumerate(self._candidates):
            if roi.tag == tag:
                self._list.item(index).setCheckState(Qt.CheckState.Unchecked)
                break
