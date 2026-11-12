from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QModelIndex, QSettings, QThreadPool, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ocr_app.application.process_images import BatchProcessingSummary
from ocr_app.domain.languages import (
    SUPPORTED_LANGUAGES,
    get_language,
    is_language_model_installed,
    reader_languages,
)
from ocr_app.domain.models import SUPPORTED_SCALE_FACTORS, ImageItem, ImageStatus, OcrResultStatus, Roi
from ocr_app.infrastructure.paths import application_directory, model_directory, result_directory
from ocr_app.infrastructure.roi_preset_store import RoiPresetStore
from ocr_app.presentation.image_drop_table import ImageDropTable
from ocr_app.presentation.image_preview import ImagePreview
from ocr_app.presentation.image_table_model import ImageTableModel
from ocr_app.presentation.language_delegate import LanguageDelegate
from ocr_app.presentation.searchable_combo_box import SearchableComboBox
from ocr_app.presentation.settings_popover import SettingsPopover
from ocr_app.presentation.worker import OcrWorker


class MainWindow(QMainWindow):
    IMAGE_FILTER = "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"

    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: OcrWorker | None = None
        self._active_screenshot_preprocessing = False
        self._static_rois: tuple[Roi, ...] = ()
        self._saved_rois: tuple[Roi, ...] = ()
        self._saved_preset_name: str | None = None
        self._model = ImageTableModel()
        self._settings = QSettings()
        self._preset_store = RoiPresetStore(application_directory() / "presets" / "roi_presets.json")

        self.setWindowTitle("이미지 OCR 도구")
        self.resize(1400, 780)
        self.setMinimumSize(900, 580)
        self._build_ui()
        self._connect_signals()
        self._apply_style()
        self._preview.set_image(None)
        self._update_footer()
        self._language_changed()
        self._reload_presets()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(18, 18, 18, 14)
        root_layout.setSpacing(12)
        self.setCentralWidget(central)

        toolbar = QHBoxLayout()
        self._add_button = QPushButton("이미지 추가")
        self._remove_button = QPushButton("선택 삭제")
        self._clear_button = QPushButton("전체 삭제")
        toolbar.addWidget(self._add_button)
        toolbar.addWidget(self._remove_button)
        toolbar.addWidget(self._clear_button)
        toolbar.addStretch(1)

        toolbar.addWidget(QLabel("기본 인식 언어"))
        self._language_combo = SearchableComboBox()
        self._language_combo.setMinimumContentsLength(18)
        for language in SUPPORTED_LANGUAGES:
            self._language_combo.addItem(language.display_name, language.code)
        saved_language = str(self._settings.value("ocr/primary_language", "ko"))
        language_index = self._language_combo.findData(saved_language)
        if language_index < 0:
            language_index = self._language_combo.findData("ko")
        self._language_combo.setCurrentIndex(language_index)
        self._language_combo.setToolTip(
            "기본값 사용인 파일에 적용됩니다. 파일별 언어는 목록에서 변경할 수 있습니다. "
            "영어가 아닌 언어에는 영어 인식을 함께 적용합니다."
        )
        toolbar.addWidget(self._language_combo)

        self._settings_button = QPushButton("⚙")
        self._settings_button.setObjectName("settingsButton")
        self._settings_button.setAccessibleName("OCR 설정")
        self._settings_button.setFixedSize(36, 34)
        self._settings_popup = SettingsPopover(self._settings_button, self)
        settings_layout = QVBoxLayout(self._settings_popup)
        settings_layout.setContentsMargins(16, 14, 16, 14)
        settings_layout.setSpacing(12)
        title = QLabel("OCR 설정")
        title.setObjectName("settingsTitle")
        settings_layout.addWidget(title)

        self._model_download_checkbox = QCheckBox("모델 자동 다운로드")
        self._model_download_checkbox.setToolTip(
            "필요한 EasyOCR 모델이 없을 때 인터넷에서 자동으로 다운로드합니다."
        )
        settings_layout.addWidget(self._model_download_checkbox)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("선택 이미지 배율"))
        scale_row.addStretch(1)
        self._scale_combo = QComboBox()
        for scale in SUPPORTED_SCALE_FACTORS:
            self._scale_combo.addItem(f"{scale}x", scale)
        self._scale_combo.setToolTip("OCR 전처리 확대 배율입니다. 최대 4배까지 선택할 수 있습니다.")
        scale_row.addWidget(self._scale_combo)
        settings_layout.addLayout(scale_row)
        scale_hint = QLabel("선택한 이미지에 적용됩니다. 여러 개 선택 가능")
        scale_hint.setObjectName("mutedLabel")
        settings_layout.addWidget(scale_hint)

        self._preprocess_checkbox = QCheckBox()
        self._preprocess_checkbox.setChecked(
            self._settings.value("ocr/screenshot_preprocessing", False, type=bool)
        )
        self._preprocess_checkbox.setToolTip(
            "터미널·콘솔 화면의 색 번짐을 제거합니다. 이 모드에서는 1x 배율을 권장합니다."
        )
        self._update_preprocess_checkbox_text(
            self._preprocess_checkbox.isChecked()
        )
        settings_layout.addWidget(self._preprocess_checkbox)
        toolbar.addWidget(self._settings_button)

        self._clear_roi_button = QPushButton("ROI 전체 삭제")
        self._run_button = QPushButton("OCR 실행")
        self._run_button.setObjectName("primaryButton")
        toolbar.addWidget(self._clear_roi_button)
        toolbar.addWidget(self._run_button)
        root_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        file_group = QGroupBox("등록된 파일")
        file_layout = QVBoxLayout(file_group)
        file_layout.setContentsMargins(10, 16, 10, 10)
        drop_hint = QLabel("이미지 파일을 이 영역으로 드래그해 추가할 수 있습니다.")
        drop_hint.setObjectName("mutedLabel")
        file_tools = QHBoxLayout()
        file_tools.addWidget(drop_hint, 1)
        self._file_language_button = QPushButton("선택 파일 언어 변경")
        self._file_language_button.setToolTip("여러 파일을 선택하면 언어를 한 번에 변경합니다.")
        file_tools.addWidget(self._file_language_button)
        file_layout.addLayout(file_tools)
        self._table = ImageDropTable()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._language_delegate = LanguageDelegate(self._table)
        self._table.setItemDelegateForColumn(
            ImageTableModel.LANGUAGE_COLUMN, self._language_delegate
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(True)
        self._table.setGridStyle(Qt.PenStyle.SolidLine)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self._model.columnCount()):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.horizontalHeader().setSectionResizeMode(
            ImageTableModel.LANGUAGE_COLUMN, QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(
            ImageTableModel.LANGUAGE_COLUMN,
            max(190, self._table.fontMetrics().horizontalAdvance("중국어(번체) (ch_tra)") + 48),
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_layout.addWidget(self._table)

        file_footer = QHBoxLayout()
        self._file_count_label = QLabel()
        self._selection_count_label = QLabel()
        file_footer.addWidget(self._file_count_label)
        file_footer.addStretch(1)
        file_footer.addWidget(self._selection_count_label)
        file_layout.addLayout(file_footer)
        splitter.addWidget(file_group)

        preview_group = QGroupBox("이미지 미리보기 및 Multi ROI")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(10, 16, 10, 10)
        preset_toolbar = QHBoxLayout()
        preset_toolbar.addWidget(QLabel("기본 ROI 프리셋"))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumContentsLength(12)
        preset_toolbar.addWidget(self._preset_combo, 1)
        self._preset_save_button = QPushButton("저장")
        self._preset_load_button = QPushButton("불러오기")
        self._preset_delete_button = QPushButton("삭제")
        self._preset_load_button.setToolTip("선택한 프리셋을 기본 ROI로 적용합니다. 파일별로 지정한 ROI는 유지됩니다.")
        self._preset_save_button.setToolTip("현재 표시된 ROI를 프리셋으로 저장합니다.")
        for button in (self._preset_save_button, self._preset_load_button, self._preset_delete_button):
            preset_toolbar.addWidget(button)
        preview_layout.addLayout(preset_toolbar)
        self._preview_splitter = QSplitter(Qt.Orientation.Vertical)
        self._preview_splitter.setChildrenCollapsible(False)
        self._preview = ImagePreview()
        self._preview.setMinimumHeight(140)
        self._preview_splitter.addWidget(self._preview)

        self._roi_table = QTableWidget(0, 5)
        self._roi_table.setHorizontalHeaderLabels(("색상", "Tag / UI ID", "영역 (x, y, w, h)", "상태", "결과"))
        self._roi_table.verticalHeader().hide()
        self._roi_table.setColumnWidth(0, 50)
        self._roi_table.setColumnWidth(1, 140)
        self._roi_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._roi_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._roi_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._roi_table.horizontalHeader().setMinimumSectionSize(45)
        self._roi_table.setMinimumHeight(160)
        self._roi_table.setAlternatingRowColors(True)
        self._roi_table.setToolTip("Tag를 편집해 UI ID를 지정합니다. 색상을 더블클릭하면 변경할 수 있습니다.")
        self._preview_splitter.addWidget(self._roi_table)
        self._preview_splitter.setSizes((320, 230))
        preview_layout.addWidget(self._preview_splitter, 1)
        self._roi_label = QLabel("ROI: 왼쪽 드래그로 영역을 추가하세요.")
        self._roi_label.setObjectName("mutedLabel")
        preview_layout.addWidget(self._roi_label)

        splitter.addWidget(preview_group)
        splitter.setSizes((650, 750))

        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_label = QLabel("준비")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        status_layout.addWidget(self._status_label, 1)
        status_layout.addWidget(self._progress_bar, 1)
        root_layout.addWidget(status_frame)

    def _connect_signals(self) -> None:
        self._add_button.clicked.connect(self._add_images)
        self._remove_button.clicked.connect(self._remove_selected)
        self._clear_button.clicked.connect(self._clear_all)
        self._clear_roi_button.clicked.connect(self._confirm_clear_rois)
        self._run_button.clicked.connect(self._run_ocr)
        self._scale_combo.currentIndexChanged.connect(self._apply_scale)
        self._preprocess_checkbox.toggled.connect(self._preprocess_toggled)
        self._model_download_checkbox.toggled.connect(self._language_changed)
        self._language_combo.currentIndexChanged.connect(self._language_changed)
        self._preview.roi_changed.connect(self._apply_roi)
        self._roi_table.cellChanged.connect(self._roi_tag_changed)
        self._roi_table.cellDoubleClicked.connect(self._roi_color_changed)
        self._preset_save_button.clicked.connect(self._save_preset)
        self._preset_load_button.clicked.connect(self._load_preset)
        self._preset_delete_button.clicked.connect(self._delete_preset)
        self._table.images_dropped.connect(self._add_image_paths)
        self._table.clicked.connect(self._edit_language_cell)
        self._table.customContextMenuRequested.connect(self._show_file_context_menu)
        self._file_language_button.clicked.connect(self._edit_selected_language)

        selection_model = self._table.selectionModel()
        selection_model.currentChanged.connect(self._current_image_changed)
        selection_model.selectionChanged.connect(lambda *_: self._update_footer())

    def _add_images(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(
            self,
            "OCR 이미지 선택",
            "",
            self.IMAGE_FILTER,
        )
        if not file_names:
            return

        self._add_image_paths(Path(name) for name in file_names)

    def _add_image_paths(self, paths: Iterable[Path]) -> None:
        previous_count = len(self._model.items)
        added = self._model.add_paths(paths)
        self._update_footer()
        if added:
            index = self._model.index(previous_count, 0)
            self._table.setCurrentIndex(index)
            self._table.selectRow(previous_count)
            self._status_label.setText(f"이미지 {added}개를 추가했습니다.")
        else:
            self._status_label.setText("이미 등록된 파일입니다.")

    def _remove_selected(self) -> None:
        rows = [index.row() for index in self._table.selectionModel().selectedRows()]
        self._model.remove_rows(rows)
        self._update_after_list_change()

    def _clear_all(self) -> None:
        self._model.clear()
        self._update_after_list_change()

    def _update_after_list_change(self) -> None:
        if not self._model.items:
            self._refresh_roi_table()
            self._preview.set_image(None)
            self._preview.set_rois(self._static_rois)
            self._roi_label.setText(f"ROI {len(self._static_rois)}개 · 이미지를 추가하면 다시 적용됩니다.")
        self._update_footer()

    def _current_image_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        item = self._item_at(current.row()) if current.isValid() else None
        if item is None:
            self._preview.set_image(None)
            self._preview.set_rois(self._static_rois)
            self._refresh_roi_table()
            return

        self._preview.set_image(item.path, self._effective_rois(item))
        self._refresh_roi_table()
        self._scale_combo.blockSignals(True)
        scale_index = self._scale_combo.findData(item.scale_factor)
        self._scale_combo.setCurrentIndex(max(0, scale_index))
        self._scale_combo.blockSignals(False)
        self._show_item_details(item)

    def _apply_scale(self) -> None:
        scale_factor = int(self._scale_combo.currentData())
        selected_rows = {index.row() for index in self._table.selectionModel().selectedRows()}
        if not selected_rows and self._table.currentIndex().isValid():
            selected_rows.add(self._table.currentIndex().row())

        for row in selected_rows:
            item = self._item_at(row)
            if item is not None:
                item.scale_factor = scale_factor
                self._model.notify_item_updated(item)

    def _edit_language_cell(self, index: QModelIndex) -> None:
        if index.column() == ImageTableModel.LANGUAGE_COLUMN:
            self._table.edit(index)
        elif index.column() == ImageTableModel.ROI_COLUMN:
            rows = [row.row() for row in self._table.selectionModel().selectedRows()]
            menu = self._build_roi_menu(rows or [index.row()])
            menu.exec(self._table.viewport().mapToGlobal(self._table.visualRect(index).bottomLeft()))
            menu.deleteLater()

    def _edit_selected_language(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            self._table.edit(self._model.index(rows[0].row(), ImageTableModel.LANGUAGE_COLUMN))

    def _build_roi_menu(self, rows: list[int], parent=None) -> QMenu:
        menu = QMenu("ROI 변경", parent or self)
        items = [self._model.items[row] for row in rows if 0 <= row < len(self._model.items)]
        try:
            names = self._preset_store.names()
        except (OSError, ValueError) as error:
            names = []
            failed = menu.addAction(f"프리셋 읽기 실패: {error}")
            failed.setEnabled(False)
        for name in [None, *names]:
            action = menu.addAction(name if name is not None else "기본 ROI 사용")
            action.setData(name)
            action.setCheckable(True)
            action.setChecked(bool(items) and all(item.roi_preset_name == name for item in items))
            action.triggered.connect(lambda checked=False, value=name: self._apply_file_preset(rows, value))
        if not names:
            empty = menu.addAction("저장된 프리셋 없음")
            empty.setEnabled(False)
        return menu

    def _build_file_context_menu(self, rows: list[int]) -> QMenu:
        menu = QMenu(self)
        menu.addMenu(self._build_roi_menu(rows, menu))
        languages = menu.addMenu("언어 변경")
        items = [self._model.items[row] for row in rows if 0 <= row < len(self._model.items)]
        for code, label in [(None, "기본 언어 사용"), *[(lang.code, lang.display_name) for lang in SUPPORTED_LANGUAGES]]:
            action = languages.addAction(label)
            action.setData(code)
            action.setCheckable(True)
            action.setChecked(bool(items) and all(item.language_code == code for item in items))
            action.triggered.connect(lambda checked=False, value=code: self._model.set_language_for_rows(rows, value))
        return menu

    def _show_file_context_menu(self, position) -> None:
        if not self._table.isEnabled():
            return
        index = self._table.indexAt(position)
        if index.isValid() and not self._table.selectionModel().isRowSelected(index.row(), QModelIndex()):
            self._table.selectRow(index.row())
        rows = [index.row() for index in self._table.selectionModel().selectedRows()]
        if not rows:
            return
        menu = self._build_file_context_menu(rows)
        menu.exec(self._table.viewport().mapToGlobal(position))
        menu.deleteLater()

    def _apply_file_preset(self, rows: list[int], name: str | None) -> None:
        try:
            rois = self._preset_store.load(name) if name is not None else ()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "ROI 프리셋 적용 실패", str(error))
            return
        for row in set(rows):
            item = self._item_at(row)
            if item is not None:
                item.roi_preset_name = name
                item.rois = rois
                item.roi_preset_snapshot = rois
                self._model.notify_item_updated(item)
        current = self._current_item()
        if current is not None:
            self._preview.set_image(current.path, self._effective_rois(current))
        self._refresh_roi_table()
        if current is not None:
            self._show_item_details(current)

    def _apply_roi(self, rois: tuple[Roi, ...]) -> None:
        item = self._current_item()
        if item is not None and item.roi_preset_name is not None:
            item.rois = tuple(rois)
            self._model.notify_item_updated(item)
        else:
            self._static_rois = tuple(rois)
            self._update_default_roi_label()
        self._refresh_roi_table()
        source = item.roi_preset_name if item is not None and item.roi_preset_name is not None else "기본 ROI"
        self._roi_label.setText(f"ROI {len(rois)}개 · {source} · 내부 우클릭으로 삭제")

    def _effective_rois(self, item: ImageItem | None) -> tuple[Roi, ...]:
        return item.rois if item is not None and item.roi_preset_name is not None else self._static_rois

    def _display_rois(self) -> tuple[Roi, ...]:
        return self._effective_rois(self._current_item())

    def _update_default_roi_label(self) -> None:
        label = "기본 ROI 사용"
        if self._saved_preset_name:
            label = f"기본 · {self._saved_preset_name}"
        if self._static_rois != self._saved_rois:
            label += " *"
        self._model.set_default_roi_label(label)

    def _confirm_clear_rois(self) -> None:
        if not self._display_rois():
            return
        answer = QMessageBox.warning(
            self,
            "ROI 전체 삭제",
            "현재 표시된 ROI 영역을 모두 삭제하시겠습니까?\n저장한 프리셋과 이전 OCR 결과는 유지됩니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._preview.clear_roi()

    def _refresh_roi_table(self) -> None:
        self._roi_table.blockSignals(True)
        self._roi_table.setRowCount(len(self._display_rois()))
        for row, roi in enumerate(self._display_rois()):
            swatch = QTableWidgetItem("●")
            swatch.setForeground(QColor(roi.color))
            swatch.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._roi_table.setItem(row, 0, swatch)
            self._roi_table.setItem(row, 1, QTableWidgetItem(roi.tag))
            bounds = QTableWidgetItem(f"{roi.x}, {roi.y}, {roi.width}, {roi.height}")
            bounds.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self._roi_table.setItem(row, 2, bounds)
        self._roi_table.blockSignals(False)
        self._update_roi_results()

    def _update_roi_results(self) -> None:
        image = self._current_item()
        results = {result.ui_id: result for result in image.results} if image else {}
        self._roi_table.blockSignals(True)
        for row, roi in enumerate(self._display_rois()):
            result = results.get(roi.tag)
            text, tooltip, color = "", "", "#aeb4bb"
            if result is not None:
                state = {OcrResultStatus.DONE: "완료", OcrResultStatus.NEED_REVIEW: "검토 필요",
                         OcrResultStatus.FAIL: "실패"}[result.status]
                text = result.extracted_text
                tooltip = result.error_message or text
                if result.confidence is not None:
                    tooltip += f"\n신뢰도: {result.confidence:.2%}"
                color = "#ff7272" if result.processing_failed else (
                    "#ffb347" if result.status == OcrResultStatus.NEED_REVIEW else "#72d98b"
                )
            elif image is not None and image.active_roi_id == roi.tag:
                state, color = "진행 중", "#45a3ff"
            elif image is not None and image.status == ImageStatus.FAILED:
                state, tooltip, color = "실패", image.error_message, "#ff7272"
            else:
                state = "대기"
            for column, value in ((3, state), (4, text)):
                cell = QTableWidgetItem(value)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                cell.setToolTip(tooltip)
                if column == 3:
                    cell.setForeground(QColor(color))
                self._roi_table.setItem(row, column, cell)
        self._roi_table.blockSignals(False)

    def _roi_tag_changed(self, row: int, column: int) -> None:
        displayed = self._display_rois()
        if column != 1 or not 0 <= row < len(displayed):
            return
        tag = self._roi_table.item(row, column).text().strip()
        if not tag or any(r.tag == tag for i, r in enumerate(displayed) if i != row):
            QMessageBox.warning(self, "UI ID 확인", "Tag는 비어 있을 수 없으며 다른 ROI와 중복될 수 없습니다.")
            self._refresh_roi_table()
            return
        rois = list(displayed)
        rois[row] = replace(rois[row], tag=tag)
        self._preview.set_rois(tuple(rois))
        self._apply_roi(tuple(rois))

    def _roi_color_changed(self, row: int, column: int) -> None:
        displayed = self._display_rois()
        if column != 0 or not 0 <= row < len(displayed):
            return
        color = QColorDialog.getColor(QColor(displayed[row].color), self, "ROI 색상")
        if color.isValid():
            rois = list(displayed)
            rois[row] = replace(rois[row], color=color.name())
            self._preview.set_rois(tuple(rois))
            self._apply_roi(tuple(rois))

    def _assign_rois_to_items(self) -> None:
        for item in self._model.items:
            item.rois = self._effective_rois(item)

    def _reload_presets(self, selected: str | None = None) -> None:
        try:
            names = self._preset_store.names()
        except (OSError, ValueError) as error:
            self._status_label.setText(f"프리셋을 읽을 수 없습니다: {error}")
            return
        self._preset_combo.clear()
        self._preset_combo.addItem("프리셋 선택", None)
        for name in names:
            self._preset_combo.addItem(name, name)
        self._preset_combo.setCurrentIndex(max(0, self._preset_combo.findData(selected)))

    def _save_preset(self) -> bool:
        item = self._current_item()
        return self._save_roi_preset(item if item is not None and item.roi_preset_name is not None else None)

    def _save_roi_preset(self, item: ImageItem | None) -> bool:
        rois = self._effective_rois(item)
        if not rois:
            QMessageBox.warning(self, "ROI 필요", "저장할 ROI를 먼저 지정해 주세요.")
            return False
        name, accepted = QInputDialog.getText(
            self, f"ROI 프리셋 저장 · {item.path.name}" if item else "기본 ROI 프리셋 저장", "이름 (같은 이름은 덮어씁니다):",
            text=(item.roi_preset_name if item else self._preset_combo.currentData()) or "",
        )
        if not accepted:
            return False
        try:
            self._preset_store.save(name, rois)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "프리셋 저장 실패", str(error))
            return False
        if item is None:
            self._saved_rois = self._static_rois
            self._saved_preset_name = name.strip()
        else:
            item.roi_preset_name = name.strip()
            item.roi_preset_snapshot = rois
            self._model.notify_item_updated(item)
        self._update_default_roi_label()
        self._reload_presets(self._saved_preset_name)
        self._status_label.setText(f"ROI 프리셋 저장: {name.strip()}")
        return True

    def _load_preset(self) -> None:
        name = self._preset_combo.currentData()
        if name is None:
            return
        try:
            rois = self._preset_store.load(name)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "프리셋 불러오기 실패", str(error))
            return
        self._static_rois = rois
        self._saved_rois = rois
        self._saved_preset_name = name
        self._update_default_roi_label()
        self._preview.set_rois(self._display_rois())
        self._refresh_roi_table()
        self._status_label.setText(f"기본 ROI 프리셋 적용: {name} · 기본 ROI 사용인 이미지에 적용")

    def _delete_preset(self) -> None:
        name = self._preset_combo.currentData()
        if name is None:
            return
        if QMessageBox.question(self, "프리셋 삭제", f"'{name}' 프리셋을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self._preset_store.delete(name)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "프리셋 삭제 실패", str(error))
            return
        if name == self._saved_preset_name:
            self._saved_rois = ()
            self._saved_preset_name = None
        for item in self._model.items:
            if item.roi_preset_name == name:
                item.roi_preset_snapshot = ()
                self._model.notify_item_updated(item)
        self._update_default_roi_label()
        self._reload_presets()
        self._status_label.setText(f"ROI 프리셋 삭제: {name}")

    @property
    def _has_unsaved_rois(self) -> bool:
        return self._static_rois != self._saved_rois or any(
            item.roi_preset_name is not None and item.rois != item.roi_preset_snapshot
            for item in self._model.items
        )

    def _save_unsaved_rois(self) -> bool:
        if self._static_rois != self._saved_rois and not self._save_roi_preset(None):
            return False
        for item in self._model.items:
            if item.roi_preset_name is not None and item.rois != item.roi_preset_snapshot:
                if not self._save_roi_preset(item):
                    return False
        return True

    def closeEvent(self, event) -> None:
        # Commit a Tag that is still being edited before checking for changes.
        focused = self.focusWidget()
        if focused is not None and self._roi_table.isAncestorOf(focused):
            focused.clearFocus()
        if not self._has_unsaved_rois:
            event.accept()
            return
        choice = QMessageBox.warning(
            self,
            "ROI 저장 확인",
            "저장하지 않은 ROI 변경 사항이 있습니다.\n프리셋으로 저장한 뒤 종료하시겠습니까?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Discard:
            event.accept()
        elif choice == QMessageBox.StandardButton.Save and self._save_unsaved_rois():
            event.accept()
        else:
            event.ignore()

    def _run_ocr(self) -> None:
        if not self._model.items:
            QMessageBox.warning(self, "처리할 파일 없음", "먼저 이미지를 추가해 주세요.")
            return

        if any(not self._effective_rois(item) for item in self._model.items):
            QMessageBox.warning(self, "ROI 필요", "ROI가 없는 이미지가 있습니다. 기본 ROI를 추가하거나 파일별 프리셋을 지정해 주세요.")
            return

        models = model_directory()
        selected_language = self._language_combo.currentData()
        if not isinstance(selected_language, str):
            QMessageBox.warning(
                self,
                "인식 언어 선택 필요",
                "검색 결과에서 사용할 언어를 선택해 주세요.",
            )
            return
        language_code = selected_language
        effective_codes = {item.language_code or language_code for item in self._model.items}
        detector_model = models / "craft_mlt_25k.pth"
        missing_languages = [
            get_language(code).name
            for code in sorted(effective_codes)
            if not is_language_model_installed(code, models)
        ]
        requires_download = (
            not detector_model.is_file()
            or bool(missing_languages)
        )
        allow_model_download = self._model_download_checkbox.isChecked()
        if requires_download and not allow_model_download:
            QMessageBox.warning(
                self,
                "EasyOCR 모델 없음",
                "필요한 EasyOCR 모델이 설치되어 있지 않습니다.\n\n"
                + (f"인식 모델 없음: {', '.join(missing_languages)}\n" if missing_languages else "")
                + ("공통 텍스트 검출 모델 없음\n" if not detector_model.is_file() else "")
                + "\n"
                "상단 톱니바퀴 설정에서 '모델 자동 다운로드'를 체크한 뒤 다시 실행해 주세요.",
            )
            return

        self._active_screenshot_preprocessing = (
            self._preprocess_checkbox.isChecked()
        )
        self._assign_rois_to_items()
        self._clear_previous_results()

        self._set_controls_enabled(False)
        preprocess_state = self._preprocess_state_text()
        if requires_download:
            self._progress_bar.setRange(0, 0)
            self._status_label.setText(
                f"필요한 OCR 모델을 준비하는 중입니다... · {preprocess_state}"
            )
        else:
            self._progress_bar.setRange(0, len(self._model.items))
            self._progress_bar.setValue(0)
            self._status_label.setText(
                f"EasyOCR 모델을 불러오는 중입니다... · {preprocess_state}"
            )

        worker = OcrWorker(
            items=self._model.items,
            model_directory=models,
            result_directory=result_directory(),
            languages=reader_languages(language_code),
            screenshot_preprocessing=self._active_screenshot_preprocessing,
            allow_model_download=allow_model_download,
        )
        worker.signals.progress.connect(self._ocr_progress)
        worker.signals.finished.connect(self._ocr_finished)
        worker.signals.failed.connect(self._ocr_failed)
        self._worker = worker
        self._thread_pool.start(worker)

    def _ocr_progress(self, completed: int, total: int, item: ImageItem) -> None:
        self._model.notify_item_updated(item)
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(completed)
        self._status_label.setText(
            f"{item.path.name}: {item.status.value} ({completed}/{total}) · "
            f"{self._preprocess_state_text()}"
        )
        if item is self._current_item():
            self._show_item_details(item)

    def _ocr_finished(self, summary: BatchProcessingSummary) -> None:
        self._set_controls_enabled(True)
        self._worker = None
        self._progress_bar.setValue(self._progress_bar.maximum())
        self._status_label.setText(
            f"완료 {summary.succeeded}개, 실패 {summary.failed}개 — "
            f"{summary.output_path.name} · {self._preprocess_state_text()}"
        )
        current = self._current_item()
        if current is not None:
            self._show_item_details(current)
        QMessageBox.information(
            self,
            "OCR 처리 완료",
            f"완료: {summary.succeeded}개\n"
            f"실패: {summary.failed}개\n\n"
            f"CSV 저장 위치:\n{summary.output_path}",
        )

    def _ocr_failed(self, message: str) -> None:
        self._set_controls_enabled(True)
        self._worker = None
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._status_label.setText("OCR 실행에 실패했습니다.")
        for item in self._model.items:
            if item.status == ImageStatus.PROCESSING:
                item.status = ImageStatus.FAILED
                item.active_roi_id = None
                item.error_message = message
                self._model.notify_item_updated(item)
        self._update_roi_results()
        QMessageBox.critical(self, "OCR 실행 오류", message)

    def _show_item_details(self, item: ImageItem) -> None:
        source = item.roi_preset_name or "기본 ROI"
        self._roi_label.setText(f"ROI {len(self._effective_rois(item))}개 · {source} · 확대 {item.scale_factor}x · 내부 우클릭으로 삭제")
        self._update_roi_results()

    def _set_controls_enabled(self, enabled: bool) -> None:
        if not enabled:
            self._settings_popup.hide_panel()
        for widget in (
            self._add_button,
            self._remove_button,
            self._clear_button,
            self._language_combo,
            self._settings_button,
            self._settings_popup,
            self._clear_roi_button,
            self._run_button,
            self._table,
            self._preview,
            self._roi_table,
            self._preset_combo,
            self._preset_save_button,
            self._preset_load_button,
            self._preset_delete_button,
            self._file_language_button,
        ):
            widget.setEnabled(enabled)
        self._update_footer()

    def _preprocess_toggled(self, checked: bool) -> None:
        self._settings.setValue("ocr/screenshot_preprocessing", checked)
        self._update_preprocess_checkbox_text(checked)

    def _update_preprocess_checkbox_text(self, checked: bool) -> None:
        state = "ON" if checked else "OFF"
        self._preprocess_checkbox.setText(f"콘솔 전처리 {state}")

    def _preprocess_state_text(self) -> str:
        state = "ON" if self._active_screenshot_preprocessing else "OFF"
        return f"콘솔 전처리 {state}"

    def _clear_previous_results(self) -> None:
        for item in self._model.items:
            item.results.clear()
            item.active_roi_id = None
            item.extracted_text = ""
            item.confidence = None
            item.error_message = ""
            item.status = ImageStatus.READY
            self._model.notify_item_updated(item)

        current = self._current_item()
        if current is not None:
            self._show_item_details(current)
        else:
            self._update_roi_results()

    def _language_changed(self) -> None:
        selected_language = self._language_combo.currentData()
        if not isinstance(selected_language, str):
            return
        language_code = selected_language
        language = get_language(language_code)
        self._settings.setValue("ocr/primary_language", language_code)
        self._model.set_default_language(language_code)
        if is_language_model_installed(language_code, model_directory()):
            self._status_label.setText(f"인식 언어: {language.name}")
        elif self._model_download_checkbox.isChecked():
            self._status_label.setText(
                f"인식 언어: {language.name} · OCR 실행 시 모델 자동 다운로드"
            )
        else:
            self._status_label.setText(
                f"인식 언어: {language.name} · 모델 없음 · 자동 다운로드 OFF"
            )

    def _current_item(self) -> ImageItem | None:
        current = self._table.currentIndex()
        return self._item_at(current.row()) if current.isValid() else None

    def _item_at(self, row: int) -> ImageItem | None:
        if 0 <= row < len(self._model.items):
            return self._model.items[row]
        return None

    def _update_footer(self) -> None:
        file_count = len(self._model.items)
        selection_count = len(self._table.selectionModel().selectedRows())
        self._file_count_label.setText(f"{file_count}개 파일")
        self._selection_count_label.setText(f"{selection_count}개 선택")
        self._file_language_button.setEnabled(selection_count > 0 and self._table.isEnabled())

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #181a1d;
                color: #e8eaed;
                font-family: "Malgun Gothic";
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #34383e;
                border-radius: 10px;
                margin-top: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QPushButton, QComboBox {
                background: #282c31;
                border: 1px solid #41464d;
                border-radius: 6px;
                padding: 7px 12px;
            }
            QPushButton:hover, QComboBox:hover { border-color: #5d9cec; }
            QPushButton#settingsButton {
                font-family: "Segoe UI Symbol";
                font-size: 20px;
                padding: 0;
            }
            QFrame#settingsPopover {
                background: #202429;
                border: 1px solid #454d57;
                border-radius: 10px;
            }
            QFrame#settingsPopover QLabel, QFrame#settingsPopover QCheckBox {
                background: transparent;
            }
            QLabel#settingsTitle { font-weight: 600; font-size: 11pt; }
            QPushButton:disabled, QComboBox:disabled { color: #71767d; }
            QCheckBox { spacing: 7px; }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid #555c65;
                border-radius: 4px;
                background: #181b1f;
            }
            QCheckBox::indicator:checked {
                background: #2f80d0;
                border-color: #58a5ef;
            }
            QCheckBox::indicator:disabled {
                background: #202328;
                border-color: #3b4046;
            }
            QPushButton#primaryButton {
                background: #246fbd;
                border-color: #3588db;
                font-weight: 600;
            }
            QTableView {
                background: #131619;
                alternate-background-color: #1d2126;
                border: none;
                gridline-color: #30353b;
                selection-background-color: #294d73;
                selection-color: #ffffff;
            }
            QTableView::item {
                padding: 0 8px;
            }
            QTableView::item:selected {
                border-top: 1px solid #4779a8;
                border-bottom: 1px solid #4779a8;
            }
            QHeaderView::section {
                background: #121416;
                border: none;
                border-bottom: 1px solid #2c3035;
                padding: 8px;
                font-weight: 600;
            }
            QProgressBar {
                background: #111315;
                border: 1px solid #34383e;
                border-radius: 5px;
                text-align: center;
                min-height: 20px;
            }
            QProgressBar::chunk { background: #246fbd; border-radius: 4px; }
            QLabel#mutedLabel { color: #aeb4bb; }
            QScrollBar:vertical {
                background: #17191c;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #454b52;
                border-radius: 5px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            """
        )
