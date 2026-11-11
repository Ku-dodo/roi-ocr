from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter


class SearchableComboBox(QComboBox):
    """A combo box that filters its items while preserving a valid selection."""

    def __init__(self) -> None:
        super().__init__()
        self._last_valid_index = -1
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        completer = QCompleter(self.model(), self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setMaxVisibleItems(12)
        self.setCompleter(completer)

        line_edit = self.lineEdit()
        line_edit.setPlaceholderText("언어명 또는 코드 검색")
        line_edit.editingFinished.connect(self._restore_valid_selection)
        self.currentIndexChanged.connect(self._remember_valid_selection)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_popup_width()

    def _update_popup_width(self) -> None:
        # A table cell may be narrow; the list still needs room for every label.
        metrics = self.view().fontMetrics()
        text_width = max(
            (metrics.horizontalAdvance(self.itemText(row)) for row in range(self.count())),
            default=0,
        )
        popup_width = max(self.width(), text_width + 56)
        self.view().setMinimumWidth(popup_width)
        self.completer().popup().setMinimumWidth(popup_width)

    def showPopup(self) -> None:
        self._update_popup_width()
        super().showPopup()

    def _remember_valid_selection(self, index: int) -> None:
        if index >= 0:
            self._last_valid_index = index

    def _restore_valid_selection(self) -> None:
        entered_text = self.currentText().strip()
        matching_index = self.findText(
            entered_text,
            Qt.MatchFlag.MatchFixedString,
        )
        if matching_index >= 0:
            self.setCurrentIndex(matching_index)
            return

        if self._last_valid_index >= 0:
            self.setCurrentIndex(self._last_valid_index)
            self.lineEdit().setText(self.itemText(self._last_valid_index))
