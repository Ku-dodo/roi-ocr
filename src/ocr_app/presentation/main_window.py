from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, QThreadPool, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
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
from ocr_app.domain.models import ImageItem, ImageStatus, Roi
from ocr_app.infrastructure.paths import model_directory, result_directory
from ocr_app.presentation.image_preview import ImagePreview
from ocr_app.presentation.image_table_model import ImageTableModel
from ocr_app.presentation.searchable_combo_box import SearchableComboBox
from ocr_app.presentation.worker import OcrWorker


class MainWindow(QMainWindow):
    IMAGE_FILTER = "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"

    def __init__(self) -> None:
        super().__init__()
        self._thread_pool = QThreadPool.globalInstance()
        self._worker: OcrWorker | None = None
        self._active_screenshot_preprocessing = False
        self._static_roi: Roi | None = None
        self._model = ImageTableModel()
        self._settings = QSettings()

        self.setWindowTitle("이미지 OCR 도구")
        self.resize(1180, 720)
        self.setMinimumSize(900, 580)
        self._build_ui()
        self._connect_signals()
        self._apply_style()
        self._preview.set_image(None)
        self._update_footer()
        self._language_changed()

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

        toolbar.addWidget(QLabel("인식 언어"))
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
            "주 인식 언어를 선택합니다. 영어가 아닌 언어에는 영어 인식을 함께 적용합니다."
        )
        toolbar.addWidget(self._language_combo)

        toolbar.addWidget(QLabel("선택 배율"))
        self._scale_combo = QComboBox()
        for scale in (1, 2, 4, 6, 8):
            self._scale_combo.addItem(f"{scale}x", scale)
        toolbar.addWidget(self._scale_combo)

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
        toolbar.addWidget(self._preprocess_checkbox)

        self._clear_roi_button = QPushButton("Static ROI 해제")
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
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(True)
        self._table.setGridStyle(Qt.PenStyle.SolidLine)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self._table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        file_layout.addWidget(self._table)

        file_footer = QHBoxLayout()
        self._file_count_label = QLabel()
        self._selection_count_label = QLabel()
        file_footer.addWidget(self._file_count_label)
        file_footer.addStretch(1)
        file_footer.addWidget(self._selection_count_label)
        file_layout.addLayout(file_footer)
        splitter.addWidget(file_group)

        preview_group = QGroupBox("이미지 미리보기 및 Static ROI")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(10, 16, 10, 10)
        self._preview = ImagePreview()
        preview_layout.addWidget(self._preview, 3)

        self._roi_label = QLabel("Static ROI: 전체 이미지")
        self._roi_label.setObjectName("mutedLabel")
        preview_layout.addWidget(self._roi_label)

        self._result_text = QPlainTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setPlaceholderText("선택한 파일의 OCR 결과가 여기에 표시됩니다.")
        self._result_text.setMaximumBlockCount(10000)
        preview_layout.addWidget(self._result_text, 1)
        splitter.addWidget(preview_group)
        splitter.setSizes((500, 660))

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
        self._clear_roi_button.clicked.connect(lambda: self._preview.clear_roi())
        self._run_button.clicked.connect(self._run_ocr)
        self._scale_combo.currentIndexChanged.connect(self._apply_scale)
        self._preprocess_checkbox.toggled.connect(self._preprocess_toggled)
        self._language_combo.currentIndexChanged.connect(self._language_changed)
        self._preview.roi_changed.connect(self._apply_roi)

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

        previous_count = len(self._model.items)
        added = self._model.add_paths(Path(name) for name in file_names)
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
            self._static_roi = None
            self._preview.set_image(None)
            self._result_text.clear()
            self._roi_label.setText("Static ROI: 전체 이미지")
        self._update_footer()

    def _current_image_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        del previous
        item = self._item_at(current.row()) if current.isValid() else None
        if item is None:
            self._preview.set_image(None)
            self._result_text.clear()
            return

        self._preview.set_image(item.path, self._static_roi)
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

    def _apply_roi(self, roi: Roi | None) -> None:
        self._static_roi = roi
        current = self._current_item()
        if current is None:
            return
        self._show_item_details(current)

    def _assign_static_roi_to_items(self) -> None:
        for item in self._model.items:
            item.roi = self._static_roi

    def _run_ocr(self) -> None:
        if not self._model.items:
            QMessageBox.warning(self, "처리할 파일 없음", "먼저 이미지를 추가해 주세요.")
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
        language = get_language(language_code)
        detector_model = models / "craft_mlt_25k.pth"
        requires_download = (
            not detector_model.is_file()
            or not is_language_model_installed(language_code, models)
        )
        self._active_screenshot_preprocessing = (
            self._preprocess_checkbox.isChecked()
        )
        self._assign_static_roi_to_items()
        self._clear_previous_results()

        self._set_controls_enabled(False)
        preprocess_state = self._preprocess_state_text()
        if requires_download:
            self._progress_bar.setRange(0, 0)
            self._status_label.setText(
                f"{language.name} OCR 모델을 다운로드하는 중입니다... · {preprocess_state}"
            )
        else:
            self._progress_bar.setRange(0, len(self._model.items))
            self._progress_bar.setValue(0)
            self._status_label.setText(
                f"EasyOCR 모델을 불러오는 중입니다... · {preprocess_state}"
            )

        worker = OcrWorker(
            items=list(self._model.items),
            model_directory=models,
            result_directory=result_directory(),
            languages=reader_languages(language_code),
            screenshot_preprocessing=self._active_screenshot_preprocessing,
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
        QMessageBox.critical(self, "OCR 실행 오류", message)

    def _show_item_details(self, item: ImageItem) -> None:
        if self._static_roi is None:
            self._roi_label.setText(
                f"Static ROI: 전체 이미지 · 확대 {item.scale_factor}x"
            )
        else:
            roi = self._static_roi
            self._roi_label.setText(
                f"Static ROI: x={roi.x}, y={roi.y}, w={roi.width}, h={roi.height} · "
                f"확대 {item.scale_factor}x"
            )

        if item.error_message:
            self._result_text.setPlainText(f"[오류]\n{item.error_message}")
        else:
            self._result_text.setPlainText(item.extracted_text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self._add_button,
            self._remove_button,
            self._clear_button,
            self._language_combo,
            self._scale_combo,
            self._preprocess_checkbox,
            self._clear_roi_button,
            self._run_button,
            self._table,
        ):
            widget.setEnabled(enabled)

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
            item.extracted_text = ""
            item.confidence = None
            item.error_message = ""
            item.status = ImageStatus.READY
            self._model.notify_item_updated(item)

        current = self._current_item()
        if current is not None:
            self._show_item_details(current)

    def _language_changed(self) -> None:
        selected_language = self._language_combo.currentData()
        if not isinstance(selected_language, str):
            return
        language_code = selected_language
        language = get_language(language_code)
        self._settings.setValue("ocr/primary_language", language_code)
        if is_language_model_installed(language_code, model_directory()):
            self._status_label.setText(f"인식 언어: {language.name}")
        else:
            self._status_label.setText(
                f"인식 언어: {language.name} · 첫 실행 시 모델 자동 다운로드"
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
            QPlainTextEdit {
                background: #121416;
                border: 1px solid #34383e;
                border-radius: 6px;
                padding: 7px;
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
