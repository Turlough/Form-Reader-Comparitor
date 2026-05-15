from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..models.fields_config import FieldConfig, FieldsConfig, ViewConfig


class DefineFieldsDialog(QDialog):
    def __init__(
        self,
        config: FieldsConfig,
        *,
        use_names_in_list: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Define Fields")
        self.resize(960, 640)
        self.setMinimumSize(800, 520)
        self._config = FieldsConfig(
            schema_version=config.schema_version,
            fields=[
                FieldConfig(
                    column=f.column,
                    name=f.name,
                    prompt=f.prompt,
                    active=f.active,
                    view=ViewConfig(
                        mode=f.view.mode,
                        rectangle=list(f.view.rectangle) if f.view.rectangle else None,
                    ),
                )
                for f in config.fields
            ],
        )
        self._use_names = use_names_in_list

        self._list = QListWidget()
        self._list.setMinimumWidth(220)
        self._name_edit = QLineEdit()
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setMinimumHeight(200)
        self._prompt_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._active_radio = QRadioButton("Active")
        self._inactive_radio = QRadioButton("Inactive")
        self._active_radio.setChecked(True)

        form = QFormLayout()
        form.addRow("Field Name:", self._name_edit)
        form.addRow("LLM Prompt:", self._prompt_edit)
        active_row = QHBoxLayout()
        active_row.addWidget(self._active_radio)
        active_row.addWidget(self._inactive_radio)
        active_row.addStretch()
        form.addRow("Status:", active_row)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addStretch()

        body = QHBoxLayout()
        body.addWidget(self._list)
        body.addLayout(right, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a field to configure:"))
        layout.addLayout(body)
        layout.addWidget(buttons)

        self._list.currentRowChanged.connect(self._on_row_changed)
        self._name_edit.textChanged.connect(self._sync_current_from_edits)
        self._prompt_edit.textChanged.connect(self._sync_current_from_edits)
        self._prompt_edit.setTabChangesFocus(True)
        self._active_radio.toggled.connect(self._sync_active_from_radio)

        self._populate_list()
        if self._list.count():
            self._list.setCurrentRow(0)

    def _populate_list(self) -> None:
        self._list.clear()
        for field in self._config.fields:
            label = field.display_label(self._use_names or bool(field.name.strip()))
            item = QListWidgetItem(label)
            item.setData(256, field.column)
            self._list.addItem(item)

    def _current_field(self) -> FieldConfig | None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._config.fields):
            return None
        return self._config.fields[row]

    def _on_row_changed(self, row: int) -> None:
        field = self._config.fields[row] if 0 <= row < len(self._config.fields) else None
        if not field:
            return
        self._name_edit.blockSignals(True)
        self._prompt_edit.blockSignals(True)
        self._name_edit.setText(field.name)
        self._prompt_edit.setPlainText(field.prompt)
        self._active_radio.setChecked(field.active)
        self._inactive_radio.setChecked(not field.active)
        self._name_edit.blockSignals(False)
        self._prompt_edit.blockSignals(False)

    def _sync_current_from_edits(self) -> None:
        field = self._current_field()
        if not field:
            return
        field.name = self._name_edit.text()
        field.prompt = self._prompt_edit.toPlainText()
        row = self._list.currentRow()
        if row >= 0:
            label = field.display_label(self._use_names or bool(field.name.strip()))
            self._list.item(row).setText(label)

    def _sync_active_from_radio(self) -> None:
        field = self._current_field()
        if field:
            field.active = self._active_radio.isChecked()

    def accept(self) -> None:
        self._sync_current_from_edits()
        self._sync_active_from_radio()
        super().accept()

    def result_config(self) -> FieldsConfig:
        return self._config
