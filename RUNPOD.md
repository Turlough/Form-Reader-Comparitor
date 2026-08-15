# RunPod (Qwen3-VL)

Operator notes for **LLM → RunPod**. App client: `src/form_reader/services/runpod_client.py`. Menu id: `runpod:<RUNPOD_MODEL>`.

Two backends share the same menu prefix. **`RUNPOD_HOST` (GPU pod) wins** if both are set.

## Desktop `.env` (app)

Restart the app after changes (`.env` loads at startup only). `RUNPOD_MODEL` must match the `id` from `GET {base}/models`.

| Variable | Purpose |
|----------|---------|
| `RUNPOD_HOST` | GPU pod OpenAI proxy, e.g. `https://{POD_ID}-8000.proxy.runpod.net` (`/v1` appended if missing) |
| `RUNPOD_ENDPOINT_ID` | Serverless endpoint id only — **not** a pod id |
| `RUNPOD_MODEL` | Exact served model id (`--served-model-name` or `/v1/models` `id`) |
| `RUNPOD_API_KEY` | Required for serverless; optional for a pod unless vLLM was started with `--api-key` |

Do **not** put worker knobs (`MAX_MODEL_LEN`, `LIMIT_MM_PER_PROMPT`, …) in the desktop `.env`.

### GPU pod (preferred)

Image `vllm/vllm-openai`, expose HTTP **8000**, bind `--host 0.0.0.0 --port 8000`. Example:

```
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 0.0.0.0 --port 8000 \
  --served-model-name qwen3-vl-8b-instruct \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768
```

App base URL: `https://{POD_ID}-8000.proxy.runpod.net/v1`

```bash
curl -sS "https://${POD_ID}-8000.proxy.runpod.net/v1/models"
curl -sS "https://${POD_ID}-8000.proxy.runpod.net/health"
```

The HTTP proxy is public (no RunPod API key) and Cloudflare-capped at **100s** (524 if slower). Use TCP from the Connect menu if form pages exceed that.

### Serverless (optional)

Base URL: `https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/openai/v1`

```bash
curl -sS "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/openai/v1/models" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}"
```

Hub/image: **vLLM worker** on a **24GB+** GPU. Prefer a **network volume**. Suggested worker env:

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

`LIMIT_MM_PER_PROMPT=image=1` is required for vision on the serverless worker. App batch reading is sequential — keep concurrency at **1** initially.

## VRAM / “No available memory for the cache blocks”

Weights left **no room for the KV cache**. Lower `MAX_MODEL_LEN`, set `MAX_NUM_SEQS` / `MAX_CONCURRENCY` to `1`, quantize, or use a larger GPU. FP16 Qwen3-VL-8B on 24GB is tight once vision + KV are included.

## Probes (scratchpad)

From repo root (loads `.env`, uses `RunPodClient`):

```bash
uv run python src/form_reader/ui/scratchpad/probe_runpod_text.py
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --large
uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --image /path/to/page.png
```

Cold start + first load can take minutes. Wait for `/health` (pod) or ready workers (serverless) before judging failures.

## Failure cheatsheet

| Symptom | Likely cause |
|---------|----------------|
| App posts to `api.runpod.ai/v2/…/openai/v1` | Pod id in `RUNPOD_ENDPOINT_ID`; set `RUNPOD_HOST` instead |
| Cloudflare **1010** | Python User-Agent blocked on the pod proxy (client sends a browser-like UA) |
| Proxy **524** / 100s timeout | Form page too slow for HTTP proxy; use TCP or a smaller image |
| OpenAI **500**, `/models` works | `RUNPOD_MODEL` ≠ served `id` (check `--served-model-name`) |
| Text OK, tiny vision OK, app / `--large` **500** | `MAX_MODEL_LEN` too small for page image tokens |
| Hang + log “No available memory for the cache blocks” | Model + context exceed GPU |
| Vision ignored / vision **500** (serverless) | Missing `LIMIT_MM_PER_PROMPT=image=1` on **worker** |

## App behaviour (Stage 1)

- Menu: **LLM → RunPod** (static list from `.env`; no `/v1/models` refresh).
- Client posts OpenAI multimodal `chat/completions` (PNG data-URL), timeout **600s**.
- Chain menus do **not** include RunPod yet.
