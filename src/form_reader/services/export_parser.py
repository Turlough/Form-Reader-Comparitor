from __future__ import annotations

import csv
from pathlib import Path

from ..models.batch import Batch, BatchRow
from ..models.fields_config import FieldsConfig, load_fields_config


def parse_export_txt(export_path: Path) -> Batch:
    export_path = export_path.resolve()
    rows: list[BatchRow] = []
    max_cols = 0

    with export_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for line in reader:
            if not line:
                continue
            relative_path = _normalize_relative_path(line[0].strip())
            values = [cell.strip() for cell in line[1:]]
            max_cols = max(max_cols, len(values))
            rows.append(BatchRow(relative_path=relative_path, ground_truth=values))

    fields_path = export_path.parent / "fields.json"
    loaded = load_fields_config(fields_path)
    if loaded and len(loaded.fields) == max_cols:
        fields_config = loaded
    elif loaded and len(loaded.fields) != max_cols:
        fields_config = FieldsConfig.for_column_count(max_cols)
        for existing in loaded.fields:
            fc = fields_config.field_for_column(existing.column)
            if fc:
                fc.name = existing.name
                fc.prompt = existing.prompt
                fc.active = existing.active
                fc.view = existing.view
    else:
        fields_config = FieldsConfig.for_column_count(max_cols)

    return Batch(
        export_path=export_path,
        rows=rows,
        fields_config=fields_config,
        column_count=max_cols,
    )


def _normalize_relative_path(raw: str) -> str:
    """Normalize Windows-style separators so the path resolves cross-platform.

    EXPORT.TXT is typically produced by Windows scanning software and may contain
    backslashes (e.g. ``IMAGES\\SCAN001.TIF``). On Linux ``Path`` treats those as
    literal characters in a single filename, which prevents the image from being
    located. Translating to forward slashes still works on Windows.
    """
    return raw.replace("\\", "/")
