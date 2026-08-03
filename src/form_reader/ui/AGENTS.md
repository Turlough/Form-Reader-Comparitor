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
- `QSettings` org `Digidoocs`, app `FormReaderComparitor` — last import folder and similar UI state
- Table: inactive columns use light gray background; reading cell highlighted; mismatch font red (case-insensitive trim)
- Stage 1 spec for panel behavior: repo-root `STAGE_1.md`

## Work Guidance

- New reader mode: add worker (or branch existing), hook in `MainWindow` batch start and LLM menu
- Long work off the UI thread; update table via signals/slots
- Retain last folder on file dialogs via `QSettings`
- `scratchpad/` holds ad-hoc probe scripts (not imported by the app)

## Verification

## Child DOX Index

- `scratchpad/` — manual RunPod/API probes (`probe_runpod_text.py`, `probe_runpod_vision.py`)
