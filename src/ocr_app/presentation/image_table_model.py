from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from ocr_app.domain.models import ImageItem, ImageStatus


class ImageTableModel(QAbstractTableModel):
    HEADERS = ("파일 이름", "형식", "배율", "상태")

    def __init__(self) -> None:
        super().__init__()
        self.items: list[ImageItem] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.items):
            return None

        item = self.items[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            values = (
                item.path.name,
                item.path.suffix.removeprefix(".").upper(),
                f"{item.scale_factor}x",
                item.status.value,
            )
            return values[index.column()]

        if role == Qt.ItemDataRole.ToolTipRole:
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
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def add_paths(self, paths: Iterable[Path]) -> int:
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
