from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models.batch import Batch
from ..models.fields_config import FieldConfig, FieldsConfig, save_fields_config
from ..services.export_parser import parse_export_txt
from ..services.ollama_client import DEFAULT_MODEL, OllamaClient
from .batch_worker import BatchPosition, BatchWorker
from .define_fields_dialog import DefineFieldsDialog
from .image_panel import ImagePanel

SETTINGS_ORG = "Digidoocs"
SETTINGS_APP = "FormReaderComparitor"
INACTIVE_COLUMN_COLOR = QColor(235, 235, 235)
READING_HIGHLIGHT = QColor(255, 255, 200)
MISMATCH_COLOR = QColor(180, 0, 0)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Form Reader Comparator")
        self.resize(1280, 720)

        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._ollama = OllamaClient()
        self._batch: Batch | None = None
        self._worker: BatchWorker | None = None
        self._model = DEFAULT_MODEL
        self._fields_defined = False
        self._current_field_column = 1
        self._reading_cell: tuple[int, int] | None = None
        self._batch_stopped = False

        self._file_list = QListWidget()
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self._image_panel = ImagePanel()
        self._image_panel.view_config_changed.connect(self._on_view_config_changed)
        self._image_panel.rectangle_drawn.connect(self._on_rectangle_drawn)

        left = QVBoxLayout()
        left.addWidget(QLabel("Images"))
        left.addWidget(self._file_list)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(180)

        center = QVBoxLayout()
        center.addWidget(QLabel("Fields"))
        center.addWidget(self._table)
        center_widget = QWidget()
        center_widget.setLayout(center)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(center_widget)
        splitter.addWidget(self._image_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 3)
        self.setCentralWidget(splitter)

        self._build_menus()
        self._wire_signals()
        self._update_batch_actions()
        self._refresh_llm_menu()

    def _build_menus(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        self._import_action = QAction("&Import...", self)
        self._import_action.triggered.connect(self._import_export)
        file_menu.addAction(self._import_action)

        fields_menu = bar.addMenu("&Fields")
        self._define_action = QAction("&Define...", self)
        self._define_action.triggered.connect(self._define_fields)
        fields_menu.addAction(self._define_action)

        field_menu = bar.addMenu("Fiel&d")
        self._read_batch_action = QAction("&Read Batch", self)
        self._read_batch_action.triggered.connect(self._start_batch)
        self._pause_action = QAction("&Pause", self)
        self._pause_action.triggered.connect(self._pause_batch)
        self._resume_action = QAction("Resu&me", self)
        self._resume_action.triggered.connect(self._resume_batch)
        self._stop_action = QAction("&Stop", self)
        self._stop_action.triggered.connect(self._stop_batch)
        field_menu.addAction(self._read_batch_action)
        field_menu.addAction(self._pause_action)
        field_menu.addAction(self._resume_action)
        field_menu.addAction(self._stop_action)

        self._llm_menu = bar.addMenu("&LLM")
        self._refresh_models_action = QAction("&Refresh models", self)
        self._refresh_models_action.triggered.connect(self._refresh_llm_menu)
        self._llm_menu.addAction(self._refresh_models_action)
        self._llm_read_action = QAction("&Read", self)
        self._llm_read_action.triggered.connect(self._start_batch)
        self._llm_menu.addAction(self._llm_read_action)
        self._llm_menu.addSeparator()
        self._model_actions: list[QAction] = []

    def _wire_signals(self) -> None:
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        self._table.currentCellChanged.connect(self._on_cell_changed)

    def _import_export(self) -> None:
        last_dir = self._settings.value("last_import_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import EXPORT.TXT",
            str(last_dir),
            "Index files (EXPORT.TXT);;Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        export_path = Path(path)
        self._settings.setValue("last_import_dir", str(export_path.parent))

        try:
            batch = parse_export_txt(export_path)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return

        self._load_batch(batch)
        self._batch_stopped = False

    def _load_batch(self, batch: Batch) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)

        self._batch = batch
        self._fields_defined = batch.fields_config.is_defined
        self._batch_stopped = False
        self._reading_cell = None
        self._current_field_column = 1
        self._image_panel.set_batch_dir(batch.batch_dir)

        self._file_list.clear()
        for row in batch.rows:
            self._file_list.addItem(row.filename())

        self._populate_table()
        self._update_batch_actions()

        if batch.rows:
            self._file_list.setCurrentRow(0)
            self._show_row_column(0, self._current_field_column)

    def _populate_table(self) -> None:
        assert self._batch
        rows = len(self._batch.rows)
        cols = self._batch.column_count
        self._table.setRowCount(rows)
        self._table.setColumnCount(cols)
        self._apply_table_headers()

        for r, batch_row in enumerate(self._batch.rows):
            for c in range(cols):
                column = c + 1
                item = QTableWidgetItem(batch_row.cell_display(column))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._style_cell_item(item, r, column)
                self._table.setItem(r, c, item)

        self._apply_inactive_column_styles()

    def _apply_table_headers(self) -> None:
        if not self._batch:
            return
        use_names = self._fields_defined
        headers = []
        for field in self._batch.fields_config.fields:
            headers.append(field.display_label(use_names))
        self._table.setHorizontalHeaderLabels(headers)

    def _apply_inactive_column_styles(self) -> None:
        if not self._batch:
            return
        brush = QBrush(INACTIVE_COLUMN_COLOR)
        for c, field in enumerate(self._batch.fields_config.fields):
            if field.active:
                continue
            for r in range(self._table.rowCount()):
                item = self._table.item(r, c)
                if item:
                    item.setBackground(brush)

    def _style_cell_item(self, item: QTableWidgetItem, row: int, column: int) -> None:
        assert self._batch
        batch_row = self._batch.rows[row]
        field = self._batch.fields_config.field_for_column(column)
        if field and not field.active:
            item.setBackground(QBrush(INACTIVE_COLUMN_COLOR))
        else:
            item.setBackground(QBrush())
        if column in batch_row.read_values and not batch_row.values_match(column):
            item.setForeground(QBrush(MISMATCH_COLOR))
        else:
            item.setForeground(QBrush())

    def _on_file_selected(self, row: int) -> None:
        if row < 0 or not self._batch:
            return
        self._table.blockSignals(True)
        self._table.setCurrentCell(row, max(0, self._current_field_column - 1))
        self._table.blockSignals(False)
        self._show_row_column(row, self._current_field_column)

    def _on_cell_changed(self, row: int, col: int, _prev_row: int, _prev_col: int) -> None:
        if row < 0 or col < 0 or not self._batch:
            return
        column = col + 1
        self._current_field_column = column
        self._file_list.blockSignals(True)
        self._file_list.setCurrentRow(row)
        self._file_list.blockSignals(False)
        self._show_row_column(row, column)

    def _show_row_column(self, row: int, column: int) -> None:
        if not self._batch:
            return
        batch_row = self._batch.rows[row]
        field = self._batch.fields_config.field_for_column(column)
        self._image_panel.set_current_field_column(column)
        self._image_panel.set_field_config(field)
        gt = batch_row.ground_truth_for(column)
        try:
            self._image_panel.show_document(
                batch_row.relative_path,
                ground_truth=gt,
                field=field,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Image display failed",
                f"Could not show {batch_row.filename()}:\n{exc}",
            )

    def _field_config_for_current_column(self) -> FieldConfig | None:
        if not self._batch:
            return None
        return self._batch.fields_config.field_for_column(self._current_field_column)

    def _save_fields_config(self) -> None:
        if not self._batch:
            return
        save_fields_config(self._batch.fields_json_path, self._batch.fields_config)

    def _on_view_config_changed(self, column: int) -> None:
        self._save_fields_config()

    def _on_rectangle_drawn(self, column: int, rect: list[float]) -> None:
        if not self._batch:
            return
        field = self._batch.fields_config.field_for_column(column)
        if field:
            field.view.rectangle = rect
        self._save_fields_config()

    def _define_fields(self) -> None:
        if not self._batch:
            QMessageBox.information(self, "No batch", "Import EXPORT.TXT first.")
            return
        use_names = self._fields_defined
        dialog = DefineFieldsDialog(
            self._batch.fields_config,
            use_names_in_list=use_names,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._batch.fields_config = dialog.result_config()
        self._fields_defined = self._batch.fields_config.is_defined
        if not self._fields_defined:
            QMessageBox.warning(
                self,
                "Incomplete",
                "Every field needs a name before batch reading.",
            )
        self._save_fields_config()
        self._apply_table_headers()
        self._apply_inactive_column_styles()

    def _refresh_llm_menu(self) -> None:
        for action in self._model_actions:
            self._llm_menu.removeAction(action)
        self._model_actions.clear()

        try:
            models = self._ollama.list_models()
        except Exception as exc:
            placeholder = QAction(f"(Ollama unavailable: {exc})", self)
            placeholder.setEnabled(False)
            self._llm_menu.addAction(placeholder)
            self._model_actions.append(placeholder)
            return

        if not models:
            empty = QAction("(no models)", self)
            empty.setEnabled(False)
            self._llm_menu.addAction(empty)
            self._model_actions.append(empty)
            return

        for name in models:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(name == self._model or name.startswith(self._model))
            action.triggered.connect(lambda checked, m=name: self._select_model(m))
            self._llm_menu.addAction(action)
            self._model_actions.append(action)

        if self._model not in models and models:
            self._model = models[0]

    def _select_model(self, model: str) -> None:
        self._model = model
        for action in self._model_actions:
            action.setChecked(action.text() == model)

    def _start_batch(self) -> None:
        if not self._batch:
            QMessageBox.information(self, "No batch", "Import EXPORT.TXT first.")
            return
        if not self._fields_defined:
            QMessageBox.warning(
                self,
                "Define fields",
                "Use Fields → Define and save all field names before reading.",
            )
            return
        if self._worker and self._worker.isRunning():
            return

        self._batch_stopped = False
        for row in self._batch.rows:
            row.read_values.clear()

        self._repopulate_table_values()
        self._worker = BatchWorker(self._batch, self._model, self._ollama, parent=self)
        self._worker.cell_started.connect(self._on_cell_started)
        self._worker.cell_completed.connect(self._on_cell_completed)
        self._worker.cell_failed.connect(self._on_cell_failed)
        self._worker.batch_finished.connect(self._on_batch_finished)
        self._worker.batch_stopped.connect(self._on_batch_stopped)
        self._worker.start()
        self._update_batch_actions(running=True)

    def _pause_batch(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.pause()
            self._update_batch_actions(running=True, paused=True)

    def _resume_batch(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.resume()
            self._update_batch_actions(running=True, paused=False)

    def _stop_batch(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._batch_stopped = True
            self._update_batch_actions()

    def _on_cell_started(self, row: int, column: int) -> None:
        self._reading_cell = (row, column)
        col_idx = column - 1
        item = self._table.item(row, col_idx)
        if item:
            item.setBackground(QBrush(READING_HIGHLIGHT))
        self._file_list.setCurrentRow(row)
        self._table.setCurrentCell(row, col_idx)
        self._show_row_column(row, column)

    def _on_cell_completed(self, row: int, column: int, value: str) -> None:
        assert self._batch
        col_idx = column - 1
        item = self._table.item(row, col_idx)
        if item:
            item.setText(value)
            self._style_cell_item(item, row, column)
        self._reading_cell = None

    def _on_cell_failed(self, row: int, column: int, message: str) -> None:
        col_idx = column - 1
        item = self._table.item(row, col_idx)
        if item:
            item.setText(f"[error: {message}]")
            item.setForeground(QBrush(MISMATCH_COLOR))
        self._reading_cell = None

    def _on_batch_finished(self) -> None:
        self._reading_cell = None
        self._update_batch_actions()

    def _on_batch_stopped(self) -> None:
        self._reading_cell = None
        self._batch_stopped = True
        self._update_batch_actions()

    def _repopulate_table_values(self) -> None:
        if not self._batch:
            return
        for r, batch_row in enumerate(self._batch.rows):
            for c in range(self._batch.column_count):
                column = c + 1
                item = self._table.item(r, c)
                if item:
                    item.setText(batch_row.cell_display(column))
                    self._style_cell_item(item, r, column)

    def _update_batch_actions(
        self,
        *,
        running: bool = False,
        paused: bool = False,
    ) -> None:
        has_batch = self._batch is not None
        can_read = has_batch and self._fields_defined and not running
        self._read_batch_action.setEnabled(can_read)
        self._llm_read_action.setEnabled(can_read)
        pause_enabled = running and not paused and not self._batch_stopped
        resume_enabled = running and paused and not self._batch_stopped
        stop_enabled = running
        self._pause_action.setEnabled(pause_enabled)
        self._resume_action.setEnabled(resume_enabled)
        self._stop_action.setEnabled(stop_enabled)
