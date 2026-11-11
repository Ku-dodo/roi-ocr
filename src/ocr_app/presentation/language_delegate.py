from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyledItemDelegate

from ocr_app.domain.languages import SUPPORTED_LANGUAGES
from ocr_app.presentation.searchable_combo_box import SearchableComboBox


class LanguageDelegate(QStyledItemDelegate):
    """Edit one language cell, applying the choice to the selected files."""

    def createEditor(self, parent, option, index):
        editor = SearchableComboBox()
        editor.setParent(parent)
        editor.setStyleSheet(
            "QComboBox { padding: 2px 6px; }"
            "QLineEdit { background: transparent; color: #e8eaed; border: none; padding: 0;"
            "selection-background-color: #294d73; selection-color: #ffffff; }"
        )
        editor.addItem("기본값 사용", None)
        for language in SUPPORTED_LANGUAGES:
            editor.addItem(language.display_name, language.code)
        rows = [row.row() for row in self.parent().selectionModel().selectedRows()]
        editor.selected_rows = rows if index.row() in rows else [index.row()]
        editor.activated.connect(lambda *_: self._commit(editor))
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.adjusted(1, 1, -1, -1))

    def setEditorData(self, editor, index):
        item = index.data(Qt.ItemDataRole.UserRole)
        editor.setCurrentIndex(editor.findData(item.language_code))
        editor.original_code = item.language_code
        editor.choice_activated = False
        editor.lineEdit().selectAll()

    def setModelData(self, editor, model, index):
        entered_text = editor.currentText().strip()
        editor._restore_valid_selection()
        if entered_text.casefold() != editor.currentText().strip().casefold():
            return
        if not editor.choice_activated and editor.currentData() == editor.original_code:
            return
        model.set_language_for_rows(editor.selected_rows, editor.currentData())

    def _commit(self, editor):
        editor.choice_activated = True
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)
