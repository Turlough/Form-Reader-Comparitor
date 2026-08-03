# Services

## Purpose

Non-UI capabilities: EXPORT.TXT parsing, first-page image load/crop, classical OCR, and LLM extraction clients.

## Ownership

- Modules under `services/`; package `__init__.py` exports only the stable import surface (`parse_export_txt`, `load_first_page_image`, `OllamaClient`) — extend `__all__` deliberately
- HTTP/API details for each provider stay in dedicated client modules

## Local Contracts

| Module | Role |
|--------|------|
| `export_parser.py` | Parse EXPORT.TXT → `Batch`; merge or create `FieldsConfig` from `fields.json` |
| `image_loader.py` | First page from PDF/TIFF/image; normalized crop; PNG bytes for vision APIs |
| `ollama_client.py` | Ollama chat/vision; `DEFAULT_MODEL`; list models for LLM menu |
| `gemini_client.py` | Gemini text API; menu ids use `gemini:` prefix via `strip_menu_prefix` |
| `lmstudio_client.py` | LM Studio OpenAI-compatible API; menu ids use `lmstudio:` prefix |
| `runpod_client.py` | RunPod serverless vLLM OpenAI API; static `RUNPOD_*` env; menu ids use `runpod:` prefix |
| `ocr_service.py` | PaddleOCR and Tesseract on normalized rectangles; `OCR_MENU_ENGINES` |
| `glm_ocr_chain.py` | Two-step: Ollama vision OCR page once per row, then text model per field; menu id `glmocr:<text_model>` |

- `GlmOcrChain.ocr_page` — full-page OCR via Ollama vision model (`GLM_OCR_MODEL`, `GLM_OCR_PROMPT`)
- `GlmOcrChain.extract_field` — routes text model to Gemini, LM Studio, or Ollama based on menu prefix
- `build_field_prompt` — wraps field prompt + OCR text; replies must be value-only
- OCR engines require `FieldConfig.has_rectangle()`; vision LLM path sends full page (optional view zoom in UI)

## Work Guidance

- Add new LLM backends as client modules with a menu prefix convention and `strip_menu_prefix`; wire in `BatchWorker` and/or `GlmOcrChain.extract_field`
- Add new OCR engines in `OcrService.read_region` and register in `OCR_MENU_ENGINES`
- Lazy-init heavy models (PaddleOCR) inside the service, not at import time
- Use `should_cancel` callbacks on long HTTP calls where workers support stop/pause

## Verification

## Child DOX Index
