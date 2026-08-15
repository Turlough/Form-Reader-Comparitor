from __future__ import annotations

from ..models.batch import Batch
from ..models.fields_config import FieldConfig
from ..services.image_loader import load_first_page_image, placeholder_image
from ..services.ocr_service import OcrService
from .batch_worker import DEFAULT_CONCURRENCY, BaseBatchWorker, BatchPosition


class OcrBatchWorker(BaseBatchWorker):
    def __init__(
        self,
        batch: Batch,
        engine: str,
        ocr: OcrService,
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
        self._engine = engine
        self._ocr = ocr

    def _read_cell(self, row_idx: int, row, field: FieldConfig) -> str:
        assert field.view.rectangle is not None
        path = row.resolve_path(self._batch.batch_dir)
        image = load_first_page_image(path) or placeholder_image()
        return self._ocr.read_region(self._engine, image, field.view.rectangle)
