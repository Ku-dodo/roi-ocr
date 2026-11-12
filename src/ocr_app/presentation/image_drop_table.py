from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QTableView


class ImageDropTable(QTableView):
    """Table view that turns dropped local image files into owned paths."""

    SUPPORTED_SUFFIXES = frozenset(
        {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    )

    images_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setDropIndicatorShown(False)

    @classmethod
    def image_paths(cls, mime_data: QMimeData) -> tuple[Path, ...]:
        if not mime_data.hasUrls():
            return ()

        paths: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.casefold() in cls.SUPPORTED_SUFFIXES:
                paths.append(path)
        return tuple(paths)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._accept_image_drop(event)

    def mousePressEvent(self, event) -> None:
        index = self.indexAt(event.position().toPoint())
        if (event.button() == Qt.MouseButton.RightButton and index.isValid()
                and self.selectionModel().isRowSelected(index.row(), index.parent())):
            event.accept()
            return
        super().mousePressEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._accept_image_drop(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = self.image_paths(event.mimeData())
        if not paths:
            event.ignore()
            return

        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.images_dropped.emit(paths)

    def _accept_image_drop(self, event: QDragEnterEvent | QDragMoveEvent) -> None:
        if self.image_paths(event.mimeData()):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()
