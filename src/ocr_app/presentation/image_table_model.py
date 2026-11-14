from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from ocr_app.domain.models import ImageItem, ImageStatus
from ocr_app.domain.languages import get_language


class ImageTableModel(QAbstractTableModel):
    HEADERS = ("파일 이름", "형식", "배율", "인식 언어", "ROI 프리셋", "상태")
    LANGUAGE_COLUMN = 3
    ROI_COLUMN = 4

    def __init__(self) -> None:
        super().__init__()
        self.items: list[ImageItem] = []
        self.default_language_code = "ko"
        self.default_roi_label = "기본 ROI 사용"

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Qt가 요청한 역할에 맞춰 셀 표시값·도움말·색상 또는 이미지 객체를 제공한다.

        Args:
            index: 조회할 셀의 모델 인덱스.
            role: Qt 데이터 역할. UserRole은 셀 편집기가 사용할 ImageItem을 요청한다.

        Returns:
            역할별 데이터 또는 None. 기본 언어·ROI는 개별 지정이 없을 때 표시하며,
            저장 스냅샷과 다른 파일별 ROI에는 변경 표시를 붙인다.
        """
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None

        item = self.items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                item.path.name,
                item.path.suffix.removeprefix(".").upper(),
                f"{item.scale_factor}x",
                (
                    get_language(item.language_code).name
                    if item.language_code is not None
                    else f"기본값 · {get_language(self.default_language_code).name}"
                ),
                ((item.roi_preset_name or "자동 찾기 초안") + (" *" if item.rois != item.roi_preset_snapshot else "")
                 if item.has_custom_rois else self.default_roi_label),
                item.status.value,
            )
            return values[index.column()]

        if role == Qt.ItemDataRole.ToolTipRole:
            if index.column() == self.ROI_COLUMN:
                return "클릭 또는 우클릭 메뉴로 ROI 프리셋을 선택합니다. 기본 ROI 사용인 파일만 기본 ROI를 따라갑니다."
            if index.column() == self.LANGUAGE_COLUMN:
                return "클릭하여 파일의 언어를 변경합니다. 기본값 사용 시 상단 언어를 따라갑니다."
            if item.error_message:
                return f"{item.path}\n\n오류: {item.error_message}"
            return str(item.path)

        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() > 0:
            return Qt.AlignmentFlag.AlignCenter

        if role == Qt.ItemDataRole.ForegroundRole:
            if item.status == ImageStatus.FAILED:
                return QColor("#ff7272")
            if item.status == ImageStatus.COMPLETED:
                return QColor("#72d98b")

        if role == Qt.ItemDataRole.UserRole:
            return item
        return None

    def set_default_language(self, code: str) -> None:
        get_language(code)
        self.default_language_code = code
        if self.items:
            self.dataChanged.emit(
                self.index(0, self.LANGUAGE_COLUMN),
                self.index(len(self.items) - 1, self.LANGUAGE_COLUMN),
            )

    def set_default_roi_label(self, label: str) -> None:
        self.default_roi_label = label
        if self.items:
            self.dataChanged.emit(self.index(0, self.ROI_COLUMN), self.index(len(self.items) - 1, self.ROI_COLUMN))

    def set_language_for_rows(self, rows: Iterable[int], code: str | None) -> None:
        if code is not None:
            get_language(code)
        for row in set(rows):
            if 0 <= row < len(self.items):
                self.items[row].language_code = code
                self.notify_item_updated(self.items[row])

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.LANGUAGE_COLUMN:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def add_paths(self, paths: Iterable[Path]) -> int:
        """절대 경로로 정규화하고 대소문자를 무시하여 중복 파일을 제외한다.

        Args:
            paths: 파일 목록에 등록할 경로들의 순회 가능한 객체.

        Returns:
            실제 추가한 이미지 개수. Qt 행 삽입 알림을 보내며 기존 행은 유지한다.
        """
        existing = {str(item.path).casefold() for item in self.items}
        new_items: list[ImageItem] = []
        for path in paths:
            resolved = path.resolve()
            key = str(resolved).casefold()
            if key not in existing:
                new_items.append(ImageItem(resolved))
                existing.add(key)

        if not new_items:
            return 0

        first = len(self.items)
        last = first + len(new_items) - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self.items.extend(new_items)
        self.endInsertRows()
        return len(new_items)

    def remove_rows(self, rows: Iterable[int]) -> None:
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self.items):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self.items[row]
                self.endRemoveRows()

    def clear(self) -> None:
        if not self.items:
            return
        self.beginResetModel()
        self.items.clear()
        self.endResetModel()

    def notify_item_updated(self, item: ImageItem) -> None:
        for row, candidate in enumerate(self.items):
            if candidate is item:
                first = self.index(row, 0)
                last = self.index(row, self.columnCount() - 1)
                self.dataChanged.emit(first, last)
                return
