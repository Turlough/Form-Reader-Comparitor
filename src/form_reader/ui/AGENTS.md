# UI

## Purpose

PyQt6 desktop shell: three-panel layout (file list, ground-truth/read table, image panel), menus for import/fields/LLM selection, and background batch workers.

## Ownership

- Modules under `ui/`; `MainWindow` is the application orchestrator
- Provider HTTP and parsing logic stay in `services/` — workers call services only

## Local Contracts

| Module | Role |
|--------|------|
| `main_window.py` | Layout, menus, import, field define, batch run/stop/pause, model menu population, table/list sync |
| `image_panel.py` | Image display, autofit/width/height, ground-truth label, selection rectangle → normalized coords |
| `define_fields_dialog.py` | Fields → Define dialog; edits `FieldsConfig` |
| `batch_worker.py` | Vision LLM per field (Ollama / Gemini / LM Studio / RunPod); `BatchPosition` for resume |
| `ocr_batch_worker.py` | Classical OCR per field using rectangle crops |
| `glm_ocr_batch_worker.py` | One OCR pass per row (cached), then text-model field extraction |

- Workers inherit `QThread`; common signals: `cell_started`, `cell_completed`, `cell_failed`, `batch_finished`, `batch_stopped`
- `QSettings` org `Digidoocs`, app `FormReaderComparitor` — keys: `last_import_dir`, `last_export_path`, `last_llm_model`, `last_ocr_engine`, `last_chain_image_model`, `last_chain_text_model`
- On startup: reopen `last_export_path` if the file still exists (silent skip on missing/unreadable); restore LLM / OCR / Chain menu selections when still available
- Table: inactive columns use light gray background; reading cell highlighted; mismatch font red (case-insensitive trim)
- Stage 1 spec for panel behavior: repo-root `STAGE_1.md`

## Work Guidance

- New reader mode: add worker (or branch existing), hook in `MainWindow` batch start and LLM menu
- Long work off the UI thread; update table via signals/slots
- Persist session UI choices via `QSettings` when the user imports a batch or selects LLM / OCR / Chain models; keep last import folder for the file dialog
- `scratchpad/` holds ad-hoc probe scripts (not imported by the app)

## Verification

## Child DOX Index

- `scratchpad/` — manual RunPod/API probes (`probe_runpod_text.py`, `probe_runpod_vision.py`)
