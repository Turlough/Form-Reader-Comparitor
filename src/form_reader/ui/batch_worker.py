from __future__ import annotations

import logging
from collections import deque
from concurrent.futures import (
    CancelledError,
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from dataclasses import dataclass

from PyQt6.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from ..models.batch import Batch
from ..models.fields_config import FieldConfig
from ..services.gemini_client import GeminiClient
from ..services.image_loader import image_to_png_bytes, load_first_page_image, placeholder_image
from ..services.lmstudio_client import LmStudioClient
from ..services.ollama_client import OllamaClient
from ..services.runpod_client import RunPodClient

logger = logging.getLogger(__name__)

CONCURRENCY_OPTIONS = (1, 2, 4, 8, 16, 32, 64)
DEFAULT_CONCURRENCY = 1


@dataclass
class BatchPosition:
    row: int
    column: int


class BaseBatchWorker(QThread):
    """QThread that reads batch cells sequentially or with a bounded thread pool."""

    cell_started = pyqtSignal(int, int)
    cell_completed = pyqtSignal(int, int, str)
    cell_failed = pyqtSignal(int, int, str)
    batch_finished = pyqtSignal()
    batch_stopped = pyqtSignal()

    def __init__(
        self,
        batch: Batch,
        *,
        start_at: BatchPosition | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._batch = batch
        self._concurrency = max(1, int(concurrency))
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
        cells = self._pending_cells()
        if self._concurrency <= 1:
            self._run_sequential(cells)
        else:
            self._run_concurrent(cells)

    def _read_cell(self, row_idx: int, row, field: FieldConfig) -> str:
        raise NotImplementedError

    def _pending_cells(self) -> list[tuple[int, int]]:
        columns = [f.column for f in self._batch.fields_config.fields]
        resume_row = self._resume_pos.row
        resume_column = self._resume_pos.column
        cells: list[tuple[int, int]] = []
        for row_idx in range(resume_row, len(self._batch.rows)):
            for column in columns:
                if row_idx == resume_row and column < resume_column:
                    continue
                field = self._batch.fields_config.field_for_column(column)
                if not field or not field.active:
                    continue
                cells.append((row_idx, column))
        return cells

    def _invoke_read(self, row_idx: int, column: int) -> str:
        row = self._batch.rows[row_idx]
        field = self._batch.fields_config.field_for_column(column)
        if field is None:
            raise RuntimeError(f"No field config for column {column}")
        return self._read_cell(row_idx, row, field)

    def _run_sequential(self, cells: list[tuple[int, int]]) -> None:
        for row_idx, column in cells:
            if self._check_stopped():
                return
            while True:
                self._wait_if_paused(row_idx, column)
                if self._check_stopped():
                    return
                self.cell_started.emit(row_idx, column)
                try:
                    value = self._invoke_read(row_idx, column)
                except InterruptedError:
                    if self._check_stopped():
                        return
                    continue
                except Exception as exc:
                    logger.exception(
                        "Batch read failed row=%d column=%d",
                        row_idx,
                        column,
                    )
                    self.cell_failed.emit(row_idx, column, str(exc))
                    break
                self._batch.rows[row_idx].read_values[column] = value
                self.cell_completed.emit(row_idx, column, value)
                break
        self.batch_finished.emit()

    def _run_concurrent(self, cells: list[tuple[int, int]]) -> None:
        pending: deque[tuple[int, int]] = deque(cells)
        in_flight: dict[Future, tuple[int, int]] = {}

        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            while pending or in_flight:
                with QMutexLocker(self._mutex):
                    stopped = self._stopped
                if stopped:
                    self._drain_in_flight(in_flight)
                    self._check_stopped()
                    return

                if self.is_paused():
                    self._collect_completed(in_flight, pending, timeout=0.05)
                    if not in_flight:
                        pos = (
                            pending[0]
                            if pending
                            else (self._resume_pos.row, self._resume_pos.column)
                        )
                        self._wait_if_paused(*pos)
                    continue

                while pending and len(in_flight) < self._concurrency:
                    row_idx, column = pending.popleft()
                    self.cell_started.emit(row_idx, column)
                    future = pool.submit(self._invoke_read, row_idx, column)
                    in_flight[future] = (row_idx, column)

                if in_flight:
                    self._collect_completed(in_flight, pending, timeout=0.05)

        self.batch_finished.emit()

    def _collect_completed(
        self,
        in_flight: dict[Future, tuple[int, int]],
        pending: deque[tuple[int, int]],
        *,
        timeout: float,
    ) -> None:
        if not in_flight:
            return
        done, _ = wait(
            list(in_flight.keys()),
            return_when=FIRST_COMPLETED,
            timeout=timeout,
        )
        for future in done:
            cell = in_flight.pop(future)
            self._settle_future(future, cell, pending)

    def _drain_in_flight(self, in_flight: dict[Future, tuple[int, int]]) -> None:
        if not in_flight:
            return
        wait(list(in_flight.keys()))
        for future, cell in list(in_flight.items()):
            self._settle_future(future, cell, pending=None)
        in_flight.clear()

    def _settle_future(
        self,
        future: Future,
        cell: tuple[int, int],
        pending: deque[tuple[int, int]] | None,
    ) -> None:
        row_idx, column = cell
        try:
            value = future.result()
        except (InterruptedError, CancelledError):
            if pending is not None:
                pending.appendleft(cell)
            return
        except Exception as exc:
            logger.exception(
                "Batch read failed row=%d column=%d",
                row_idx,
                column,
            )
            self.cell_failed.emit(row_idx, column, str(exc))
            return
        self._batch.rows[row_idx].read_values[column] = value
        self.cell_completed.emit(row_idx, column, value)

    def _wait_if_paused(self, row: int, column: int) -> None:
        while True:
            with QMutexLocker(self._mutex):
                if self._stopped:
                    return
                if not self._paused:
                    self._cancel_requested = False
                    return
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


class BatchWorker(BaseBatchWorker):
    def __init__(
        self,
        batch: Batch,
        model: str,
        ollama: OllamaClient,
        gemini: GeminiClient | None = None,
        lmstudio: LmStudioClient | None = None,
        runpod: RunPodClient | None = None,
        start_at: BatchPosition | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        parent=None,
    ) -> None:
        super().__init__(
            batch,
            start_at=start_at,
            concurrency=concurrency,
            parent=parent,
        )
        self._model = model
        self._ollama = ollama
        self._gemini = gemini
        self._lmstudio = lmstudio
        self._runpod = runpod

    def _read_cell(self, row_idx: int, row, field: FieldConfig) -> str:
        path = row.resolve_path(self._batch.batch_dir)
        image = load_first_page_image(path) or placeholder_image()
        png = image_to_png_bytes(image)
        prompt = field.prompt.strip() or f"What is the value for {field.name}?"
        logger.debug(
            "BatchWorker _read_cell model=%r field=%r prompt=%r image_bytes=%d",
            self._model,
            field.name,
            prompt,
            len(png),
        )

        api_model = GeminiClient.strip_menu_prefix(self._model)
        if api_model is not None:
            logger.debug("Routing to Gemini api_model=%r", api_model)
            if not self._gemini or not self._gemini.is_configured:
                raise RuntimeError("Gemini is not configured (set GEMINI_API_KEY).")
            return self._gemini.extract_field(
                api_model,
                prompt,
                png,
                should_cancel=self._should_cancel,
            )

        api_model = LmStudioClient.strip_menu_prefix(self._model)
        if api_model is not None:
            logger.debug("Routing to LM Studio api_model=%r", api_model)
            if not self._lmstudio:
                raise RuntimeError("LM Studio client is not configured.")
            return self._lmstudio.extract_field(
                api_model,
                prompt,
                png,
                should_cancel=self._should_cancel,
            )

        api_model = RunPodClient.strip_menu_prefix(self._model)
        if api_model is not None:
            logger.debug("Routing to RunPod api_model=%r", api_model)
            if not self._runpod or not self._runpod.is_configured:
                hint = (
                    self._runpod.missing_config_hint() if self._runpod else ""
                )
                raise RuntimeError(
                    "RunPod is not configured" + (f" {hint}" if hint else ".")
                )
            return self._runpod.extract_field(
                api_model,
                prompt,
                png,
                should_cancel=self._should_cancel,
            )

        logger.debug("Routing to Ollama model=%r", self._model)
        return self._ollama.extract_field(
            self._model,
            prompt,
            png,
            should_cancel=self._should_cancel,
        )
