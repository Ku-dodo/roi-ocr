from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyledItemDelegate

from ocr_app.domain.languages import SUPPORTED_LANGUAGES
from ocr_app.presentation.searchable_combo_box import SearchableComboBox


class LanguageDelegate(QStyledItemDelegate):
    """Edit one language cell, applying the choice to the selected files."""

    def createEditor(self, parent, option, index):
        """언어 검색 편집기를 만들고 변경을 적용할 선택 행을 고정한다.

        Args:
            parent: 편집기의 부모 위젯.
            option: Qt 셀 표시 옵션. 생성 단계에서는 사용하지 않는다.
            index: 편집할 셀. 다중 선택 밖의 셀이면 해당 행만 대상으로 삼는다.

        Returns:
            기본값 사용 항목과 언어 목록을 담은 SearchableComboBox.
        """
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
        """유효한 언어 선택만 편집 시작 시의 선택 행 전체에 반영한다.

        Args:
            editor: 입력 문자열과 선택 원본을 보관한 언어 편집기.
            model: 이미지 목록 모델.
            index: Qt가 전달한 편집 셀. 적용 행은 editor.selected_rows를 사용한다.

        Returns:
            None. 무효 입력을 복원했거나 실제 선택이 바뀌지 않았으면 반영하지 않는다.
        """
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
