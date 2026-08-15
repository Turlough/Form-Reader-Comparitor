from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..db.repository import RunStatRecord, RunStatsRepository

HEADERS = (
    "Started",
    "Workers",
    "Method",
    "Models",
    "Cells read",
    "Accurate",
    "Accuracy",
    "Time",
    "Status",
    "Batch",
)


def format_duration_ms(ms: int) -> str:
    if ms < 0:
        ms = 0
    total_s = ms / 1000
    if total_s < 60:
        return f"{total_s:.1f}s"
    minutes, sec = divmod(total_s, 60)
    if minutes < 60:
        return f"{int(minutes)}m {sec:.1f}s"
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}h {minutes}m {int(sec)}s"


def format_accuracy(cells_read: int, cells_accurate: int) -> str:
    if cells_read <= 0:
        return "—"
    return f"{100.0 * cells_accurate / cells_read:.1f}%"


def format_batch(export_path: str) -> str:
    if not export_path:
        return ""
    return str(Path(export_path).parent)


class StatsTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[RunStatRecord] = []

    def set_rows(self, rows: list[RunStatRecord]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        if parent and parent.isValid():
            return 0
        return len(HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(HEADERS):
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(row, col)
        if role == Qt.ItemDataRole.UserRole:
            return self._sort_value(row, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 9:
                return row.export_path
            return self._display(row, col)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 4, 5, 6, 7):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None

    def _display(self, row: RunStatRecord, col: int) -> str:
        if col == 0:
            return row.started_at.strftime("%Y-%m-%d %H:%M:%S")
        if col == 1:
            return str(row.worker_threads)
        if col == 2:
            return row.method
        if col == 3:
            return row.models
        if col == 4:
            return str(row.cells_read)
        if col == 5:
            return str(row.cells_accurate)
        if col == 6:
            return format_accuracy(row.cells_read, row.cells_accurate)
        if col == 7:
            return format_duration_ms(row.duration_ms)
        if col == 8:
            return row.status
        if col == 9:
            return format_batch(row.export_path)
        return ""

    def _sort_value(self, row: RunStatRecord, col: int):
        if col == 0:
            return row.started_at.timestamp()
        if col == 1:
            return row.worker_threads
        if col == 4:
            return row.cells_read
        if col == 5:
            return row.cells_accurate
        if col == 6:
            if row.cells_read <= 0:
                return -1.0
            return row.cells_accurate / row.cells_read
        if col == 7:
            return row.duration_ms
        return self._display(row, col).lower()


class ColumnFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filters: dict[int, str] = {}
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_column_filter(self, column: int, text: str) -> None:
        self._filters[column] = text.strip()
        self.invalidateFilter()

    def clear_filters(self) -> None:
        self._filters.clear()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        model = self.sourceModel()
        if model is None:
            return True
        for col, needle in self._filters.items():
            if not needle:
                continue
            index = model.index(source_row, col, source_parent)
            displayed = str(model.data(index, Qt.ItemDataRole.DisplayRole) or "")
            if needle.casefold() not in displayed.casefold():
                return False
        return True


class StatsWindow(QMainWindow):
    def __init__(
        self,
        repository: RunStatsRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Run statistics")
        self.resize(1180, 520)
        self._repository = repository
        self._model = StatsTableModel(self)
        self._proxy = ColumnFilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._filter_combos: list[QComboBox] = []

        toolbar = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        clear = QPushButton("Clear filters")
        clear.clicked.connect(self._clear_filters)
        toolbar.addWidget(refresh)
        toolbar.addWidget(clear)
        toolbar.addStretch()
        self._count_label = QLabel()
        toolbar.addWidget(self._count_label)

        self._filter_widget = QWidget()
        self._filter_layout = QHBoxLayout(self._filter_widget)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(0)
        for col, header in enumerate(HEADERS):
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )
            combo.setMinimumWidth(0)
            completer = combo.completer()
            if completer is not None:
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            line = combo.lineEdit()
            if line is not None:
                line.setPlaceholderText(header)
            combo.currentTextChanged.connect(
                lambda text, c=col: self._on_filter_changed(c, text)
            )
            self._filter_layout.addWidget(combo)
            self._filter_combos.append(combo)

        self._filter_scroll = QScrollArea()
        self._filter_scroll.setWidget(self._filter_widget)
        self._filter_scroll.setWidgetResizable(False)
        self._filter_scroll.setFixedHeight(32)
        self._filter_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._filter_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._filter_scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setWordWrap(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.sectionResized.connect(self._sync_filter_widths)
        self._table.horizontalScrollBar().valueChanged.connect(
            self._filter_scroll.horizontalScrollBar().setValue
        )

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self._filter_scroll)
        layout.addWidget(self._table)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.refresh()
        self._table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def refresh(self) -> None:
        current_filters = [combo.currentText() for combo in self._filter_combos]
        self._model.set_rows(self._repository.list_all())
        self._table.resizeColumnsToContents()
        self._rebuild_filter_options(current_filters)
        self._sync_filter_widths()
        self._update_count()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_filter_widths()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_filter_widths()

    def _on_filter_changed(self, column: int, text: str) -> None:
        self._proxy.set_column_filter(column, text)
        self._update_count()

    def _clear_filters(self) -> None:
        for combo in self._filter_combos:
            combo.blockSignals(True)
            combo.setCurrentText("")
            combo.blockSignals(False)
        self._proxy.clear_filters()
        self._update_count()

    def _rebuild_filter_options(self, current_filters: list[str]) -> None:
        for col, combo in enumerate(self._filter_combos):
            values = sorted(
                {
                    str(
                        self._model.data(
                            self._model.index(row, col),
                            Qt.ItemDataRole.DisplayRole,
                        )
                        or ""
                    )
                    for row in range(self._model.rowCount())
                }
            )
            values = [v for v in values if v]
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(values)
            if col < len(current_filters):
                combo.setCurrentText(current_filters[col])
            combo.blockSignals(False)
            self._proxy.set_column_filter(col, combo.currentText())

    def _sync_filter_widths(self) -> None:
        header = self._table.horizontalHeader()
        total = 0
        for col, combo in enumerate(self._filter_combos):
            width = header.sectionSize(col)
            combo.setFixedWidth(width)
            total += width
        self._filter_widget.setFixedWidth(max(total, self._table.viewport().width()))
        self._filter_scroll.horizontalScrollBar().setValue(
            self._table.horizontalScrollBar().value()
        )

    def _update_count(self) -> None:
        shown = self._proxy.rowCount()
        total = self._model.rowCount()
        if shown == total:
            self._count_label.setText(f"{total} run{'s' if total != 1 else ''}")
        else:
            self._count_label.setText(f"{shown} of {total} runs")
