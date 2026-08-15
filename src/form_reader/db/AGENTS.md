# Database

## Purpose

Versioned SQLite persistence for **run statistics** (not the full Stage 2 schema in `PLAN.md`). Alembic migrates the schema on app launch.

## Ownership

- Modules under `db/`; Alembic scripts under `db/alembic/`
- UI must go through `RunStatsRepository` — do not issue SQL from widgets
- Repo-root `alembic.ini` is for developer CLI; runtime uses `migrate.alembic_config()`

## Local Contracts

| Module | Role |
|--------|------|
| `paths.py` | DB file location; `FORM_READER_DB` overrides default `GenericDataLocation/Digidoocs/FormReaderComparitor/form_reader.db` |
| `models.py` | SQLAlchemy `RunStat` (`run_stats` table) |
| `engine.py` | Cached SQLite engine / session factory |
| `repository.py` | `RunStatRecord` and `RunStatsRepository.record` / `list_all` |
| `migrate.py` | `init_db()` → Alembic `upgrade head`, then dispose engine |
| `alembic/` | env, versions; current head `001` creates `run_stats` |

`run_stats` columns: `started_at`, `finished_at`, `duration_ms` (pause time excluded), `worker_threads`, `method` (`LLM` / `OCR` / `Chain`), `models`, `cells_read`, `cells_accurate` (case-insensitive trim vs ground truth), `status` (`Completed` / `Stopped`), `export_path`.

Failed cells are not in `BatchRow.read_values` and do not count as read.

## Work Guidance

- Schema changes: add an Alembic revision under `alembic/versions/`, update `models.py` to match, bump nothing else
- Developer CLI from repo root: `uv run alembic current` / `uv run alembic upgrade head` (same path as the app: `FORM_READER_DB` or the default app-data file).
- The app calls `init_db()` after `QApplication` exists so `QStandardPaths` works
- Do not implement the Stage 2 batches/rows/reader-results schema here unless that milestone is in progress

## Verification

- `FORM_READER_DB` pointing at a temp file, then `init_db()`, must create `run_stats` and `alembic_version` at head `001`
- `uv run alembic current` against that same path must report `001 (head)`

## Child DOX Index
