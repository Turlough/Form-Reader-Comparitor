# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Repository purpose

PyQt6 desktop app that compares **form-reading techniques** against ground-truth batches indexed by **EXPORT.TXT**. Stage 1 (current): single-batch evaluation with vision LLMs (Ollama), optional OCR engines (Paddle, Tesseract), and a **glm-ocr chain** (OCR pass + text model for field extraction). Stage 2 (planned): SQLite persistence, multi-reader runs, Levenshtein scoring, web NL analytics — see `PLAN.md`.

Terminology: `GLOSSARY.md` (batch, index, ground truth, EXPORT.TXT). Stage 1 UX spec: `STAGE_1.md`.

## Project layout

- Entry: repo-root `main.py` delegates to `form_reader.main:main`; CLI script `form-reader` from `pyproject.toml`
- Package: `src/form_reader/` — `main.py`, `models/`, `services/`, `ui/`
- Durable docs at repo root: `README.md`, `PLAN.md`, `STAGE_1.md`, `GLOSSARY.md`, `RUNPOD.md`
- Dependencies: [uv](https://docs.astral.sh/uv/) (`pyproject.toml`, `uv.lock`); run `uv sync` after clone or dependency changes
- Config: `.env` at repo root (template `env.example`); loaded from package dir or ancestors in `form_reader.main`

### Configuration (env)

- `OLLAMA_HOST` — Ollama API base URL
- `GEMINI_API_KEY` — Google Gemini text completions (menu prefix `gemini:`)
- `LMSTUDIO_HOST` — LM Studio OpenAI-compatible API (menu prefix `lmstudio:`)
- `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT_ID`, `RUNPOD_MODEL` — RunPod serverless vLLM (menu prefix `runpod:`; all three required); operator notes in `RUNPOD.md`
- `GLM_OCR_MODEL`, `GLM_OCR_PROMPT` — vision OCR model and prompt for glm-ocr chain
- `TESSERACT_CMD` — optional path to tesseract binary (Windows auto-discovery otherwise)

### Batch workflow (Stage 1)

1. **File → Import** — parse `EXPORT.TXT` (CSV, no headers; col 0 = relative image path; first page only for multipage TIFF/PDF); last path and LLM/OCR/Chain selections restore on next launch via `QSettings`
2. **Fields → Define** — field names, LLM prompts, active/inactive, per-field view settings; persisted as `fields.json` beside EXPORT.TXT
3. **LLM** menu — choose Ollama model, Gemini, LM Studio, RunPod, OCR engine, or glm-ocr chain (`glmocr:<text_model>`)
4. **Fields → Read Batch** — sequential read; table shows ground truth then read values; mismatches in red; inactive columns gray

### Conventions

- Follow conventional commits; reference GitLab issues with `#<number>`
- Reader/extraction backends live in `services/`; UI workers in `ui/` must not embed provider HTTP details
- Future Stage 2 `Reader` protocol and SQLite schema belong in `PLAN.md` until implemented — do not assume they exist in code yet

## Core Contract

- AGENTS.md files are binding work contracts for their subtrees
- Work products, source materials, instructions, records, assets, and durable docs must stay understandable from the nearest applicable AGENTS.md plus every parent AGENTS.md above it

## Read Before Editing

1. Read the root AGENTS.md
2. Identify every file or folder you expect to touch
3. Walk from the repository root to each target path
4. Read every AGENTS.md found along each route
5. If a parent AGENTS.md lists a child AGENTS.md whose scope contains the path, read that child and continue from there
6. Use the nearest AGENTS.md as the local contract and parent docs for repo-wide rules
7. If docs conflict, the closer doc controls local work details, but no child doc may weaken DOX

Do not rely on memory. Re-read the applicable DOX chain in the current session before editing.

## Update After Editing

Every meaningful change requires a DOX pass before the task is done.

Update the closest owning AGENTS.md when a change affects:

- purpose, scope, ownership, or responsibilities
- durable structure, contracts, workflows, or operating rules
- required inputs, outputs, permissions, constraints, side effects, or artifacts
- user preferences about behavior, communication, process, organization, or quality
- AGENTS.md creation, deletion, move, rename, or index contents

Update parent docs when parent-level structure, ownership, workflow, or child index changes. Update child docs when parent changes alter local rules. Remove stale or contradictory text immediately. Small edits that do not change behavior or contracts may leave docs unchanged, but the DOX pass still must happen.

## Hierarchy

- Root AGENTS.md is the DOX rail: project-wide instructions, global preferences, durable workflow rules, and the top-level Child DOX Index
- Child AGENTS.md files own domain-specific instructions and their own Child DOX Index
- Each parent explains what its direct children cover and what stays owned by the parent
- The closer a doc is to the work, the more specific and practical it must be

## Child Doc Shape

- Create a child AGENTS.md when a folder becomes a durable boundary with its own purpose, rules, responsibilities, workflow, materials, or quality standards
- Work Guidance must reflect the current standards of the project or user instructions; if there are no specific standards or instructions yet, leave it empty
- Verification must reflect an existing check; if no verification framework exists yet, leave it empty and update it when one exists

Default section order:

- Purpose
- Ownership
- Local Contracts
- Work Guidance
- Verification
- Child DOX Index

## Style

- Keep docs concise, current, and operational
- Document stable contracts, not diary entries
- Put broad rules in parent docs and concrete details in child docs
- Prefer direct bullets with explicit names
- Do not duplicate rules across many files unless each scope needs a local version
- Delete stale notes instead of explaining history
- Trim obvious statements, repeated rules, misplaced detail, and warnings for risks that no longer exist

## Closeout

1. Re-check changed paths against the DOX chain
2. Update nearest owning docs and any affected parents or children
3. Refresh every affected Child DOX Index
4. Remove stale or contradictory text
5. Run existing verification when relevant
6. Report any docs intentionally left unchanged and why

## User Preferences

When the user requests a durable behavior change, record it here or in the relevant child AGENTS.md

## Child DOX Index

- `src/form_reader/AGENTS.md` — Python package: entrypoint, batch import, field config, orchestration
  - `src/form_reader/models/AGENTS.md` — batch rows, field config schema, `fields.json`
  - `src/form_reader/services/AGENTS.md` — EXPORT parsing, image load, OCR and LLM clients, glm-ocr chain, RunPod
  - `src/form_reader/ui/AGENTS.md` — PyQt6 main window, panels, dialogs, batch workers
