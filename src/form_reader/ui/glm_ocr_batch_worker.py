from __future__ import annotations

import logging
import threading

from ..models.batch import Batch
from ..models.fields_config import FieldConfig
from ..services.glm_ocr_chain import GlmOcrChain
from ..services.image_loader import image_to_png_bytes, load_first_page_image, placeholder_image
from .batch_worker import DEFAULT_CONCURRENCY, BaseBatchWorker, BatchPosition

logger = logging.getLogger(__name__)


class GlmOcrBatchWorker(BaseBatchWorker):
    def __init__(
        self,
        batch: Batch,
        image_model: str,
        text_model: str,
        chain: GlmOcrChain,
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
        self._image_model = image_model
        self._text_model = text_model
        self._chain = chain
        self._ocr_lock = threading.Lock()
        self._ocr_row_locks: dict[int, threading.Lock] = {}
        self._ocr_cache: dict[int, str] = {}
        self._ocr_errors: dict[int, BaseException] = {}

    def _read_cell(self, row_idx: int, row, field: FieldConfig) -> str:
        ocr_text = self._ocr_for_row(row_idx, row)
        return self._chain.extract_field(
            self._text_model,
            field.prompt,
            field.name,
            ocr_text,
            should_cancel=self._should_cancel,
        )

    def _ocr_for_row(self, row_idx: int, row) -> str:
        while True:
            with self._ocr_lock:
                cached = self._ocr_cache.get(row_idx)
                if cached is not None:
                    return cached
                error = self._ocr_errors.get(row_idx)
                if error is not None:
                    raise error
                row_lock = self._ocr_row_locks.setdefault(row_idx, threading.Lock())

            if not row_lock.acquire(blocking=False):
                with row_lock:
                    continue

            try:
                with self._ocr_lock:
                    cached = self._ocr_cache.get(row_idx)
                    if cached is not None:
                        return cached
                    error = self._ocr_errors.get(row_idx)
                    if error is not None:
                        raise error

                path = row.resolve_path(self._batch.batch_dir)
                image = load_first_page_image(path) or placeholder_image()
                png = image_to_png_bytes(image)
                ocr_text = self._chain.ocr_page(
                    self._image_model,
                    png,
                    should_cancel=self._should_cancel,
                )
                with self._ocr_lock:
                    self._ocr_cache[row_idx] = ocr_text
                return ocr_text
            except InterruptedError:
                raise
            except Exception as exc:
                logger.exception("GLM-OCR page transcription failed row=%d", row_idx)
                with self._ocr_lock:
                    self._ocr_errors[row_idx] = exc
                raise
            finally:
                row_lock.release()
