# Models

## Purpose

In-memory domain types for imported batches, ground-truth rows, and per-field configuration persisted as `fields.json`.

## Ownership

- Modules under `models/`; re-export public types from `models/__init__.py` when added
- CSV/EXPORT parsing and file I/O stay in `services/export_parser.py` and `fields_config.py` load/save helpers

## Local Contracts

- **Column 0** (EXPORT.TXT) is the relative image path; model columns are **1-based** index fields matching ground-truth columns after the path
- `BatchRow.ground_truth` — list aligned to columns 1..n; `read_values` maps column → extracted text
- `BatchRow.values_match` — case-insensitive trim compare between read value and ground truth
- `FieldsConfig.is_defined` — all fields must have non-empty `name` before batch read is allowed
- `FieldConfig.view` — `ViewMode`: `auto`, `width`, `height`, `rectangle` (normalized 0–1 coords); rectangle used by OCR path and optional LLM zoom
- `fields.json` schema version: `SCHEMA_VERSION` in `fields_config.py`; bump when breaking on-disk shape

## Work Guidance

- Extend `FieldConfig` / `FieldsConfig` for new per-field metadata before touching UI or workers
- When EXPORT column count changes vs saved `fields.json`, `export_parser` merges by column index — preserve that behavior when editing import logic

## Verification

## Child DOX Index
