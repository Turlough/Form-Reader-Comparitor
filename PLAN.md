# Plan: Form reader comparitor — Stage 1 and foundations

This document turns `README.md` into an implementable roadmap. No code assumptions beyond what follows.

---

## Goals (Stage 1)

1. **Desktop app (PyQt6)**  
   Import ground truth from CSV, configure which OCR/readers run, create each **run** with a **name** and **description** (for retrospective lists and reports), execute with the chosen timing strategy, persist results and per-row metrics (Levenshtein vs ground truth).

2. **Web app + LLM**  
   Natural language queries against the persisted database. Use **one** model suited to statistical / structured querying over results (as in README Stage 1).

3. **Non-goals for initial cut**  
   Perfect handling of every edge CSV variant beyond agreed rules; full barcode pipeline details; maximizing UI polish before core pipeline works end-to-end.

---

## CSV and ground truth (your answers §1–§3)

- **Format:** Simple CSV; fields that contain commas are **RFC-style quoted** (`"` delimiters). Encoding: **UTF-8** by default; document BOM handling if encountered.
- **No fixed sample:** Design for **schema variability**: every batch can have a **different column count and meaning**, except **column 0 is always the relative image path**.
- **Multipage inputs:** Paths may point to multipage TIFF/PDF; **only the first page** is processed (consistent with README).
- **Column semantics:** Columns after the path are “ground-truth fields” in order; names are optional metadata (either auto-derived `col_1`, `col_2`, … or user-editable aliases stored with the batch). Readers may return **fewer/more/sparse** columns; comparison strategy must tolerate mismatch (see Accuracy).

**Import responsibilities**

- Parse CSV robustly (standard library CSV or well-understood dialect).
- Create a **batch** record plus **rows** keyed by normalized path string (and optional file hash later for duplicate detection).
- Store **canonical column indices** per batch (`0 = path`, `1..n = gt fields`), not assumptions about universal headers.

---

## Accuracy (your answer §2)

- **Metric:** Levenshtein distance.
- **Scope:** **Per row** — one distance (or explicit rule for combining distances — see below) between ground-truth text and OCR output **for that row**.
- **Combining columns for “per row”:** Define a deterministic rule stored in metadata, e.g. **concatenate** all comparable field values with a delimiter not present in text (or per-field distances then sum/mean — **pick one**, document it; README says “measured across all fields”; **recommended:** sum of per-field Levenshtein over aligned comparable columns, skipping missing pairs, with documented behavior when counts differ).

**Later (NL queries / aggregates)**  
Batch-level aggregates (means, distributions, reader rankings) live in analytical queries over stored per-row scores, not necessarily in the first UI.

---

## Reader outputs vs varying columns (your answer §3)

- **Run configuration:** For each reader, define either:
  - a **positional mapping** (reader output column *j* ↔ batch GT column *k*), or  
  - a **name-based mapping** once readers emit named fields,  
  falling back to “same column count/order as GT” **only when** user confirms defaults.
- **Storage:** Persist **reader raw outputs** as structured blobs (JSON) per row/run/technique alongside normalized cells for comparison, so retrospective remapping remains possible without re-running OCR.

---

## Execution modes (your answer §4)

User-selectable modes:

| Mode        | Behaviour |
|------------|-----------|
| **Sequential** | One document (or one reader?) at a time according to documented policy — **recommended:** sequential over **documents** per reader, readers run one after another or in isolation per timing block (must be spelled out in UX copy). |
| **Concurrent** | Parallelize within documented bounds (worker pool / process pool); respect memory and GPU/API limits per reader type. |
| **Both**     | Two **full passes** over the batch: run entire batch in concurrent mode once, measure wall and per-document times; repeat in sequential mode. **Default.**

**Recorded timings**

- Wall time per **run** per **mode**.
- Optionally per-document start/end timestamps for finer analysis later.

Avoid double-counting: store **two** timing blocks per run when “Both”, or distinct sub-run identifiers linked to the same logical experiment.

---

## Persistence (your answer §5)

- **SQLite** as primary store.

**Suggested logical entities**

- **Batches:** id, imported_at, CSV path/description, dialect notes, optional column alias map JSON.
- **Batch rows:** id, batch_id, relative_path (and resolved absolute path optional), gt_fields JSON/array.
- **Zone templates (per batch):** optional for LLM-only runs; **required** when pure OCR participates. Fields: batch_id, page index (typically `0` for first page), coordinate space (`normalized_0_1` vs pixels at reference DPI), ROI list keyed to GT column indices (or named slots aligned to mappings); version for template edits across runs.
- **Reader registry:** id, display name, **reader family** (see OCR vs LLM below), `needs_zoning`, implementation kind (`tesseract`, …, `vision_llm_ollama`, …), config JSON (models, langs, endpoints, prompts, concurrency hints).
- **Runs:** id, batch_id, **name** (short label; recommend **unique per batch**, enforce in app or via DB constraint), **description** (free text for context—hardware, hypotheses, Reader subset rationale, notebook-style notes), created_at, modes_used (`seq` \| `conc` \| `both`), subset of readers, environment metadata (hostname, GPU, reader versions). Name and description surface in desktop run history and in web/NL tooling as human-facing metadata (include in API/schema hints for the analytics model).
- **Run executions / timing:** run_id, mode (`seq`/`conc`), started_at, finished_at.
- **Reader results:** run_id, row_id, reader_id, mode segment, raw_output JSON, normalized_cells JSON, **per-row Levenshtein** (scalar), notes (errors, timeouts).

Indexing: `(run_id, row_id, reader_id, mode)`, `(batch_id, relative_path)` for lookups; index or unique tuple on `(batch_id, run.name)` if uniqueness per batch is enforced.

Backup/export: periodic `.dump` or file copy; optional export to Parquet later for heavier analytics — not required Stage 1.

---

## OCR vs LLM (extraction readers)

Cross-reference: `README.md` **§ OCR vs LLM**.

**Behavioral split (from README)**

- **Vision / extraction LLMs** can answer *content queries* without fixed layout—for example prompts like “What is the surname, forename, and DOB of this person”—and lean on comprehension to locate field text **without prescribing a zone** on the page first.
- **Pure OCR engines** (e.g. Tesseract-style): you must define the **rectangle** (ROI) where each corresponding field lives **before** text is extracted from that crop.

Therefore:

- **A separate zoning UI** is **required** when any chosen method is pure OCR-driven: users define rectangles (per batch template, or per-document pattern—implementation detail). The same tooling **may optionally** constrain or guide LLM-based reads but is **not mandatory** when only LLMs are selected.
- It is **common that only LLMs** are chosen; README treats **field zoning as a secondary concern** in those scenarios—defer strict zoning workflows until OCR readers join the mix, but keep the pipeline ready (see persistence below).

**Complementary comparison (engineering)**

| Aspect | Pure OCR / classical stacks | Vision-LLM extraction |
|--------|-----------------------------|-------------------------|
| Locating fields | ROIs mandatory before read | Natural-language prompts; optional overlays |
| Setup burden | Rectangle editor + persistence | Prompts + model/API config |
| Examples | Tesseract, PaddleOCR, EasyOCR, Surya, DocTR, Kraken | e.g. glm-ocr via Ollama, other vision-capable models |
| Throughput profile | Often more parallel-friendly per crop | Typically higher latency; cap concurrency accordingly |

Evaluation remains one pipeline once reader outputs are normalized to comparable **cells** (Levenshtein as elsewhere in this plan).

**Plan implications**

- One **`Reader` protocol**; implementations declare **`reader_family`** (`ocr_pure` \| `vision_llm` \| hybrid adapters) plus **`needs_zoning: bool`** (true for pure OCR as above).
- **Zoning subsystem:** persist ROIs tied to batch + target page (**first page only** per README) + field alignment to GT columns; validate “zones complete” before starting a run that includes pure OCR readers; **warn-skip vs block** configurable for optional LLM+zone use.
- **Do not conflate** extraction LLMs with the **analytics LLM** (web NL queries on SQLite): different prompts, endpoints, and cost model.
- Per-reader **resource policy**: e.g. lower parallel caps for LLM workers than for local OCR crops.
- Store **per-reader config snapshot** on each run (model, prompts, zone template version) for reproducibility.

---

## OCR / extraction strategy pattern

README calls for interchangeable techniques across **both** OCR-style engines and vision-LLM extractors. **Architecture:**

- **`Reader` interface/protocol:** `capabilities`, `reader_family`, `needs_zoning`, `warmup()`, `read_first_page(document_path, zone_template | None, **kwargs) -> structured result` (pure OCR: `zone_template` required; LLM: typically `None` unless optional zones supplied), optional `estimated_cost`/resource hints.
- **Adapters** per implementation; unify output to `{ "cells": [...], "extras": {...} }` so scoring and DB storage stay identical.
- **Plugin-style registration:** core app lists readers from entry points or a registry dict for Stage 1 simplicity.

Defer binding every backend in day one; **stub + one reference reader per family** (one **pure OCR** with minimal rectangle workflow, one **vision LLM**) validates both **zoning** and **prompt-only** paths, then add readers incrementally.

---

## Applications

### Desktop (PyQt6)

Rough screen flow:

1. New batch → pick CSV → preview first *N* rows and inferred columns.
2. Configure readers subset + mapping defaults (OCR vs LLM readers may show different option panels—prompts vs engines).
3. **Zoning editor (when needed):** if any selected reader has `needs_zoning`, open the **separate rectangle-definition UI** and save a **zone template** for the batch (first page); **skippable** when the selection is **LLM-only** (zoning remains optional for optional LLM+ROI experiments).
4. **New run:** enter **name** (required) and **description** (optional but encouraged for later you); choose timing mode (**Sequential / Concurrent / Both**; **default Both**).
5. Execute → progress, cancel, logs.
6. **Run history / picker:** list runs by name, batch, date, mode; open details including description and environment snapshot.
7. Results table: paths, GT snippet, outputs, Levenshtein; drill-down to stored raw JSON.
8. Open DB location / “open web query” launcher (optional shortcut).

Threading: workers off UI thread; cap concurrency in settings.

### Web + NL query

- Thin **API layer** reading SQLite **read-only** (or WAL with single writer discipline).
- **One** LLM for analytics questions: prompt includes **schema description** + safe query hints; include **run `name` and `description`** in the schema summary so users can ask “compare the handwritten batch run *foo* vs *bar*”. Prefer **structured intermediate step** (e.g. SQL or dataframe operation generated then executed in sandbox with allowlisted operations) rather than unrestricted SQL from the model — exact mechanism is an implementation detail in a later milestone; **Stage 1** can ship with **preset queries** plus NL if risk is manageable.

Authentication and deployment: localhost-first; document securing if exposed beyond LAN.

---

## Phased milestones

| Phase | Deliverable |
|-------|--------------|
| **M1** | SQLite schema, CSV import batch+rows, in-memory sanity checks. |
| **M2** | Reader abstraction (`needs_zoning`, LLM vs pure OCR) + **zoning model** in DB; one reader per family end-to-end; per-row score; timing modes; runs persist **name** + **description**. |
| **M3** | PyQt6 UI: import, reader config, **zoning editor when required**, named run, **run history**, results. |
| **M4** | Second reader + concurrent/failure hardening; validate mixed runs (OCR+LLM) vs LLM-only (no blocking on zones). |
| **M5** | Web NL query MVP (readonly DB + statistical model + guarded query path). |

---

## Open decisions (to lock before coding)

These are internal product choices; they do not block writing schema migrations but block final scoring UX:

1. **Per-row Levenshtein:** sum over aligned fields vs normalized concatenation — choose one rule and expose it in the UI/help.
2. **Sequential definition:** sequential across **documents** with **parallel readers** disallowed vs fully single-threaded system-wide — affects fairness when comparing libraries.
3. **Column alignment default** when counts differ: left-align positional, truncate/pad behavior, explicit “unmapped reader column” buckets.
4. **Zoning scope:** one template per batch vs per-image ROIs; coordinate system; how to handle slight scan misalignment (future: none in Stage 1 beyond fixed template).

Once those are chosen, README + this plan anchor implementation without sample files.

---

## References

- Ground truth CSV rules, batch categories, **OCR vs LLM** (rectangles mandatory for pure OCR; optional otherwise; zoning secondary when LLM-only): root `README.md`.
- Persistence: SQLite; execution defaults: **Both** passes where applicable; every run has **name** and **description** for retrospective review and NL queries.
