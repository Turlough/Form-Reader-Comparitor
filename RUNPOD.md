# RunPod (Qwen3-VL serverless)

Operator notes for **LLM → RunPod** against a RunPod Serverless **vLLM** endpoint. App client: `src/form_reader/services/runpod_client.py`. Menu id: `runpod:<RUNPOD_MODEL>`.

## Desktop `.env` (app)

All three required; restart the app after changes (`.env` loads at startup only).

| Variable | Purpose |
|----------|---------|
| `RUNPOD_API_KEY` | RunPod API key (`Authorization: Bearer …`) |
| `RUNPOD_ENDPOINT_ID` | Serverless endpoint id (URL segment only — not the display name) |
| `RUNPOD_MODEL` | **Exact** model id returned by `/openai/v1/models` |

Base URL used by the app:

`https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1`

Do **not** put worker knobs (`MAX_MODEL_LEN`, `LIMIT_MM_PER_PROMPT`, …) in the desktop `.env` — they only apply on the RunPod endpoint.

### Model id must match the worker

vLLM may serve a lowercased id. After the endpoint is up:

```bash
curl -sS "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/openai/v1/models" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

Set `RUNPOD_MODEL` to the `id` field (e.g. `qwen/qwen3-vl-8b-instruct`), not necessarily the Hugging Face casing (`Qwen/Qwen3-VL-8B-Instruct`). A mismatch often surfaces as a generic OpenAI-path **500**.

## RunPod console (worker)

Deploy Hub/image: **vLLM worker** (`runpod-workers/worker-vllm` / `runpod/worker-v1-vllm:…`) on a **24GB+** GPU (RTX 4090 / A5000 class). Prefer a **network volume** so cold starts do not re-download weights.

Recommended worker env for **Qwen3-VL-8B-Instruct** + form pages:

```
MODEL_NAME=Qwen/Qwen3-VL-8B-Instruct
LIMIT_MM_PER_PROMPT=image=1
MAX_MODEL_LEN=4096
GPU_MEMORY_UTILIZATION=0.90
DTYPE=float16
DOWNLOAD_DIR=/runpod-volume
MAX_NUM_SEQS=1
MAX_CONCURRENCY=1
```

Notes:

- `LIMIT_MM_PER_PROMPT=image=1` is required for vision; without it, image requests often fail.
- `MAX_MODEL_LEN` is a trade-off: form-page images consume many vision tokens. **1024** is usually too low for full pages (tiny test images may still work). **4096** is a practical starting point for this app; raise toward **8192** only if KV cache still allocates.
- App batch reading is sequential — keep concurrency at **1** initially.

After deploy: copy endpoint id → `RUNPOD_ENDPOINT_ID`; set `RUNPOD_MODEL` from `/openai/v1/models` as above.

## VRAM / “No available memory for the cache blocks”

That log means weights left **no room for the KV cache**. Requests hang or fail.

Mitigations (worker side):

1. Lower `MAX_MODEL_LEN` (e.g. 4096 → 2048) **or**
2. Lower `MAX_NUM_SEQS` / `MAX_CONCURRENCY` to `1` **or**
3. Quantize / use an FP8 checkpoint **or**
4. Move to a larger GPU (48GB)

FP16 Qwen3-VL-8B on 24GB is tight once vision + KV are included.

## Probes (scratchpad)

From repo root (loads `.env`):

```bash
# Text only — proves endpoint + model id
uv run python src/form_reader/ui/scratchpad/probe_runpod_text.py

# Vision — 1x1 PNG (sanity); then form-sized page
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --large
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --image /path/to/page.png
```

Also useful:

```bash
# Workers / job counters
curl -sS "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/health" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

Cold start + first load can take minutes. Prefer waiting until `/health` shows `ready` workers before judging failures.

## Failure cheatsheet

| Symptom | Likely cause |
|---------|----------------|
| `endpoint not found` | Placeholder or wrong `RUNPOD_ENDPOINT_ID`; app not restarted after `.env` edit |
| OpenAI **500**, text probe fails, `/models` works | `RUNPOD_MODEL` ≠ served `id` (check casing) |
| Text OK, tiny vision OK, app / `--large` **500** | `MAX_MODEL_LEN` too small for page image tokens |
| Hang + log “No available memory for the cache blocks” | Model + context exceed GPU; lower `MAX_MODEL_LEN` or free VRAM |
| Vision ignored / vision **500** | Missing `LIMIT_MM_PER_PROMPT=image=1` on **worker** |
| Generic OpenAI **500** with little detail | Check RunPod worker logs; try native `/runsync` or the probes above |

## App behaviour (Stage 1)

- Menu: **LLM → RunPod** (static list from `.env`; no `/v1/models` refresh).
- Client posts OpenAI multimodal `chat/completions` (PNG data-URL), timeout **600s**.
- Chain menus do **not** include RunPod yet.
