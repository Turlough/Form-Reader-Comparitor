from __future__ import annotations

import logging
import os
from typing import Callable

from .gemini_client import GeminiClient
from .lmstudio_client import LmStudioClient
from .ollama_client import DEFAULT_MODEL, OllamaClient

logger = logging.getLogger(__name__)

GLMOCR_MENU_PREFIX = "glmocr:"

DEFAULT_OCR_MODEL = os.environ.get("GLM_OCR_MODEL", DEFAULT_MODEL)
DEFAULT_OCR_PROMPT = os.environ.get(
    "GLM_OCR_PROMPT",
    "Transcribe all text visible on this form page. "
    "Preserve layout where helpful and include both printed and handwritten text. "
    "Output plain text only.",
)


def chain_menu_id(text_model: str) -> str:
    return f"{GLMOCR_MENU_PREFIX}{text_model}"


def is_chain_model(menu_model: str) -> bool:
    return menu_model.startswith(GLMOCR_MENU_PREFIX)


def strip_chain_prefix(menu_model: str) -> str:
    return menu_model[len(GLMOCR_MENU_PREFIX) :]


def build_field_prompt(field_prompt: str, field_name: str, ocr_text: str) -> str:
    instruction = field_prompt.strip() or f"What is the value for {field_name}?"
    return (
        f"{instruction}\n\n"
        "The following is OCR text from the form page:\n\n"
        "---\n"
        f"{ocr_text}\n"
        "---\n\n"
        "Reply with only the extracted value, no explanation."
    )


class GlmOcrChain:
    def __init__(
        self,
        ollama: OllamaClient,
        *,
        gemini: GeminiClient | None = None,
        lmstudio: LmStudioClient | None = None,
        ocr_model: str | None = None,
        ocr_prompt: str | None = None,
    ) -> None:
        self._ollama = ollama
        self._gemini = gemini
        self._lmstudio = lmstudio
        self._ocr_model = ocr_model or DEFAULT_OCR_MODEL
        self._ocr_prompt = ocr_prompt or DEFAULT_OCR_PROMPT

    def ocr_page(
        self,
        image_png: bytes,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        logger.debug(
            "GlmOcrChain ocr_page model=%r image_bytes=%d",
            self._ocr_model,
            len(image_png),
        )
        return self._ollama.extract_field(
            self._ocr_model,
            self._ocr_prompt,
            image_png,
            should_cancel=should_cancel,
        )

    def extract_field(
        self,
        text_model: str,
        field_prompt: str,
        field_name: str,
        ocr_text: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        prompt = build_field_prompt(field_prompt, field_name, ocr_text)
        logger.debug(
            "GlmOcrChain extract_field text_model=%r field=%r",
            text_model,
            field_name,
        )

        api_model = GeminiClient.strip_menu_prefix(text_model)
        if api_model is not None:
            if not self._gemini or not self._gemini.is_configured:
                raise RuntimeError("Gemini is not configured (set GEMINI_API_KEY).")
            return self._gemini.complete_text(
                api_model,
                prompt,
                should_cancel=should_cancel,
            )

        api_model = LmStudioClient.strip_menu_prefix(text_model)
        if api_model is not None:
            if not self._lmstudio:
                raise RuntimeError("LM Studio client is not configured.")
            return self._lmstudio.complete_text(
                api_model,
                prompt,
                should_cancel=should_cancel,
            )

        return self._ollama.complete_text(
            text_model,
            prompt,
            should_cancel=should_cancel,
        )
