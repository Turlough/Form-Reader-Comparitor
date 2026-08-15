# form_reader package

## Purpose

Installable Python package for the Form Reader Comparator desktop app: import ground-truth batches, configure index fields, run extraction (vision LLM, OCR, or glm-ocr chain), compare read values to ground truth in the UI, and record run statistics.

## Ownership

- `main.py` — logging, `.env` load, exception hook, `QApplication` bootstrap, Alembic `init_db()`
- Subpackages: `models/` (data), `services/` (I/O and readers), `db/` (run stats SQLite), `ui/` (PyQt6)
- Repo-root `main.py` is a thin launcher only; durable logic stays here

## Local Contracts

- `Batch` is the in-memory working set after import; run-level stats persist in SQLite (`db/`) — not the full Stage 2 schema
- Field configuration round-trips through `fields.json` in the batch folder (`export_path.parent`)
- `MainWindow` owns client instances (`OllamaClient`, `GeminiClient`, `LmStudioClient`, `RunPodClient`, `OcrService`, `GlmOcrChain`) and selects the appropriate batch worker by menu model choice
- Batch reading uses one QThread worker plus a thread pool sized by the **Concurrency** menu (1, 2, 4, 8, 16, 32, 64); workers emit Qt signals for cell progress — see `ui/AGENTS.md`
- Menu model prefixes route to backends: `gemini:`, `lmstudio:`, `runpod:`, `glmocr:` (chain), plain name → Ollama
- Each finished or stopped batch run is recorded via `RunStatsRepository` (workers, method/models, cells read/accurate, duration excluding pause)

## Work Guidance

- New extraction backends: implement in `services/`, wire menu prefix and worker branch in `ui/main_window.py`
- Keep `export_parser.parse_export_txt` the single import path for EXPORT.TXT
- Image handling: first page only via `services/image_loader.py`
- Schema changes for run stats: Alembic revision under `db/alembic/versions/` plus matching `db/models.py`

## Verification

## Child DOX Index

- `models/AGENTS.md` — `Batch`, `BatchRow`, `FieldsConfig`, `FieldConfig`, view modes
- `services/AGENTS.md` — parsers, clients, OCR, glm-ocr chain
- `db/AGENTS.md` — SQLite `run_stats`, Alembic, repository
- `ui/AGENTS.md` — windows, panels, dialogs, workers
