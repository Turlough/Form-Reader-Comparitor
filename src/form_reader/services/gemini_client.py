from __future__ import annotations

import base64
import os
from typing import Callable

import httpx
import logging

logger = logging.getLogger(__name__)

GEMINI_MENU_PREFIX = "gemini:"

# Vision-capable models for field extraction (menu id = prefix + model id).
DEFAULT_GEMINI_VISION_MODELS = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
)


class GeminiClient:
    _BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None, timeout: float = 300.0) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")).strip()
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def list_menu_models(self) -> list[str]:
        if not self.is_configured:
            return []
        return [f"{GEMINI_MENU_PREFIX}{m}" for m in DEFAULT_GEMINI_VISION_MODELS]

    @staticmethod
    def strip_menu_prefix(menu_model: str) -> str | None:
        if menu_model.startswith(GEMINI_MENU_PREFIX):
            return menu_model[len(GEMINI_MENU_PREFIX) :]
        return None

    def _generate_content(
        self,
        api_model: str,
        parts: list[dict],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        url = f"{self._BASE}/models/{api_model}:generateContent"
        payload = {"contents": [{"parts": parts}]}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            logger.debug(
                "Gemini response status=%s body=%s",
                response.status_code,
                response.text[:2000],
            )
            if should_cancel and should_cancel():
                raise InterruptedError("Cancelled")
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                try:
                    err = exc.response.json().get("error", {})
                    detail = err.get("message", detail)
                    logger.error("Gemini HTTP error: %s", err or detail)
                except Exception:
                    logger.error("Gemini HTTP error: %s", detail)
                raise RuntimeError(detail or str(exc)) from exc

            data = response.json()

        if err := data.get("error"):
            msg = err.get("message", str(err))
            logger.error("Gemini error: %s", msg)
            raise RuntimeError(msg)

        text = _concat_response_text(data)
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")
        return text

    def complete_text(
        self,
        api_model: str,
        prompt: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        logger.debug("Gemini complete_text model=%r prompt=%r", api_model, prompt)
        result = self._generate_content(
            api_model,
            [{"text": prompt}],
            should_cancel=should_cancel,
        )
        logger.debug("Gemini complete_text result=%r", result)
        return result

    def extract_field(
        self,
        api_model: str,
        prompt: str,
        image_png: bytes,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        logger.debug(
            "Gemini extract_field model=%r prompt=%r image_bytes=%d",
            api_model,
            prompt,
            len(image_png),
        )

        b64 = base64.b64encode(image_png).decode("ascii")
        result = self._generate_content(
            api_model,
            [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/png", "data": b64}},
            ],
            should_cancel=should_cancel,
        )
        logger.debug("Gemini extract_field result=%r", result)
        return result


def _concat_response_text(data: dict) -> str:
    parts_out: list[str] = []
    for cand in data.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            t = part.get("text")
            if t:
                parts_out.append(t)
    return "".join(parts_out).strip()
