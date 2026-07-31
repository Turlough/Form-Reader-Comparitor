from __future__ import annotations

import logging

from PyQt6.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from ..models.batch import Batch
from ..models.fields_config import FieldConfig
from ..services.glm_ocr_chain import GlmOcrChain, strip_chain_prefix
from ..services.image_loader import image_to_png_bytes, load_first_page_image, placeholder_image
from .batch_worker import BatchPosition

logger = logging.getLogger(__name__)


class GlmOcrBatchWorker(QThread):
    cell_started = pyqtSignal(int, int)
    cell_completed = pyqtSignal(int, int, str)
    cell_failed = pyqtSignal(int, int, str)
    batch_finished = pyqtSignal()
    batch_stopped = pyqtSignal()

    def __init__(
        self,
        batch: Batch,
        chain_model: str,
        chain: GlmOcrChain,
        start_at: BatchPosition | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._batch = batch
        self._text_model = strip_chain_prefix(chain_model)
        self._chain = chain
        self._mutex = QMutex()
        self._paused = False
        self._stopped = False
        self._cancel_requested = False
        self._stop_emitted = False
        self._ocr_cache: dict[int, str] = {}
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

            try:
                ocr_text = self._ocr_for_row(row_idx, row)
            except InterruptedError:
                if self._check_stopped():
                    return
                continue
            except Exception as exc:
                logger.exception("GLM-OCR page transcription failed row=%d", row_idx)
                for column in columns[start_idx:]:
                    field = self._batch.fields_config.field_for_column(column)
                    if not field or not field.active:
                        continue
                    self.cell_started.emit(row_idx, column)
                    self.cell_failed.emit(row_idx, column, str(exc))
                row_idx += 1
                resume_column = columns[0] if columns else 1
                continue

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
                    value = self._read_cell(field, ocr_text)
                except InterruptedError:
                    if self._check_stopped():
                        return
                    continue
                except Exception as exc:
                    logger.exception(
                        "GLM-OCR field extraction failed row=%d column=%d text_model=%r",
                        row_idx,
                        column,
                        self._text_model,
                    )
                    self.cell_failed.emit(row_idx, column, str(exc))
                    continue

                row.read_values[column] = value
                self.cell_completed.emit(row_idx, column, value)

            row_idx += 1
            resume_column = columns[0] if columns else 1

        self.batch_finished.emit()

    def _ocr_for_row(self, row_idx: int, row) -> str:
        if row_idx in self._ocr_cache:
            return self._ocr_cache[row_idx]

        while self._wait_if_paused(row_idx, self._resume_pos.column):
            if self._check_stopped():
                raise InterruptedError("Cancelled")

        path = row.resolve_path(self._batch.batch_dir)
        image = load_first_page_image(path) or placeholder_image()
        png = image_to_png_bytes(image)
        ocr_text = self._chain.ocr_page(png, should_cancel=self._should_cancel)
        self._ocr_cache[row_idx] = ocr_text
        return ocr_text

    def _read_cell(self, field: FieldConfig, ocr_text: str) -> str:
        return self._chain.extract_field(
            self._text_model,
            field.prompt,
            field.name,
            ocr_text,
            should_cancel=self._should_cancel,
        )

    def _wait_if_paused(self, row: int, column: int) -> bool:
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
