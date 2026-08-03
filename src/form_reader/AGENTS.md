# form_reader package

## Purpose

Installable Python package for the Form Reader Comparator desktop app: import ground-truth batches, configure index fields, run extraction (vision LLM, OCR, or glm-ocr chain), and compare read values to ground truth in the UI.

## Ownership

- `main.py` — logging, `.env` load, exception hook, `QApplication` bootstrap
- Subpackages: `models/` (data), `services/` (I/O and readers), `ui/` (PyQt6)
- Repo-root `main.py` is a thin launcher only; durable logic stays here

## Local Contracts

- `Batch` is the in-memory working set after import; no SQLite yet (Stage 2)
- Field configuration round-trips through `fields.json` in the batch folder (`export_path.parent`)
- `MainWindow` owns client instances (`OllamaClient`, `GeminiClient`, `LmStudioClient`, `RunPodClient`, `OcrService`, `GlmOcrChain`) and selects the appropriate batch worker by menu model choice
- Batch reading is **sequential** (one thread per worker); workers emit Qt signals for cell progress — see `ui/AGENTS.md`
- Menu model prefixes route to backends: `gemini:`, `lmstudio:`, `runpod:`, `glmocr:` (chain), plain name → Ollama

## Work Guidance

- New extraction backends: implement in `services/`, wire menu prefix and worker branch in `ui/main_window.py`
- Keep `export_parser.parse_export_txt` the single import path for EXPORT.TXT
- Image handling: first page only via `services/image_loader.py`

## Verification

## Child DOX Index

- `models/AGENTS.md` — `Batch`, `BatchRow`, `FieldsConfig`, `FieldConfig`, view modes
- `services/AGENTS.md` — parsers, clients, OCR, glm-ocr chain
- `ui/AGENTS.md` — windows, panels, dialogs, workers
