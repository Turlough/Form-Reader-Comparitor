from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from ..models.batch import Batch
from ..models.fields_config import FieldConfig
from ..services.gemini_client import GeminiClient
from ..services.image_loader import image_to_png_bytes, load_first_page_image, placeholder_image
from ..services.ollama_client import OllamaClient


@dataclass
class BatchPosition:
    row: int
    column: int


class BatchWorker(QThread):
    cell_started = pyqtSignal(int, int)
    cell_completed = pyqtSignal(int, int, str)
    cell_failed = pyqtSignal(int, int, str)
    batch_finished = pyqtSignal()
    batch_stopped = pyqtSignal()

    def __init__(
        self,
        batch: Batch,
        model: str,
        ollama: OllamaClient,
        gemini: GeminiClient | None = None,
        start_at: BatchPosition | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._batch = batch
        self._model = model
        self._ollama = ollama
        self._gemini = gemini
        self._mutex = QMutex()
        self._paused = False
        self._stopped = False
        self._cancel_requested = False
        self._stop_emitted = False
        first_col = batch.fields_config.fields[0].column if batch.fields_config.fields else 1
        self._resume_pos = start_at or BatchPosition(0, first_col)

    def pause(self) -> None:
        with QMutexLocker(self._mutex):
            self._paused = True
            self._cancel_requested = True

    def resume(self) -> None:
        with QMutexLocker(self._mutex):
            self._paused = False
            self._cancel_requested = False

    def stop(self) -> None:
        with QMutexLocker(self._mutex):
            self._stopped = True
            self._cancel_requested = True

    def is_paused(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._paused

    def _should_cancel(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._cancel_requested

    def run(self) -> None:
        row_idx = self._resume_pos.row
        resume_column = self._resume_pos.column

        while row_idx < len(self._batch.rows):
            if self._check_stopped():
                return

            row = self._batch.rows[row_idx]
            columns = [f.column for f in self._batch.fields_config.fields]
            start_idx = 0
            for i, col in enumerate(columns):
                if col >= resume_column:
                    start_idx = i
                    break

            for column in columns[start_idx:]:
                if self._check_stopped():
                    return

                while self._wait_if_paused(row_idx, column):
                    if self._check_stopped():
                        return

                field = self._batch.fields_config.field_for_column(column)
                if not field or not field.active:
                    continue

                self.cell_started.emit(row_idx, column)
                try:
                    value = self._read_cell(row, field)
                except InterruptedError:
                    if self._check_stopped():
                        return
                    continue
                except Exception as exc:
                    self.cell_failed.emit(row_idx, column, str(exc))
                    continue

                row.read_values[column] = value
                self.cell_completed.emit(row_idx, column, value)

            row_idx += 1
            resume_column = columns[0] if columns else 1

        self.batch_finished.emit()

    def _wait_if_paused(self, row: int, column: int) -> bool:
        """Block while paused. Returns True if we should retry same cell after resume."""
        while True:
            with QMutexLocker(self._mutex):
                paused = self._paused
                stopped = self._stopped
                if stopped:
                    return False
                if not paused:
                    self._cancel_requested = False
                    return False
            self._resume_pos = BatchPosition(row, column)
            self.msleep(50)

    def _check_stopped(self) -> bool:
        with QMutexLocker(self._mutex):
            if self._stopped:
                if not self._stop_emitted:
                    self._stop_emitted = True
                    self.batch_stopped.emit()
                return True
        return False

    def _read_cell(self, row, field: FieldConfig) -> str:
        path = row.resolve_path(self._batch.batch_dir)
        image = load_first_page_image(path) or placeholder_image()
        png = image_to_png_bytes(image)
        prompt = field.prompt.strip() or f"What is the value for {field.name}?"
        api_model = GeminiClient.strip_menu_prefix(self._model)
        if api_model is not None:
            if not self._gemini or not self._gemini.is_configured:
                raise RuntimeError("Gemini is not configured (set GEMINI_API_KEY).")
            return self._gemini.extract_field(
                api_model,
                prompt,
                png,
                should_cancel=self._should_cancel,
            )
        return self._ollama.extract_field(
            self._model,
            prompt,
            png,
            should_cancel=self._should_cancel,
        )
