from __future__ import annotations

import base64
import json
import logging
import os
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "glm-ocr"


class OllamaClient:
    def __init__(self, host: str | None = None, timeout: float = 300.0) -> None:
        resolved = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).strip()
        self.host = resolved.rstrip("/")
        self.timeout = timeout
        logger.debug(
            "OllamaClient initialized host=%s timeout=%s",
            self.host,
            self.timeout,
        )

    @staticmethod
    def _format_error(body: str) -> str:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return body.strip()
        error = data.get("error", body)
        if isinstance(error, dict):
            return str(error.get("message") or error)
        if isinstance(error, str):
            try:
                inner = json.loads(error)
            except json.JSONDecodeError:
                return error
            if isinstance(inner, dict):
                nested = inner.get("error", inner)
                if isinstance(nested, dict):
                    return str(nested.get("message") or nested)
                return str(nested)
        return body.strip()

    def list_models(self) -> list[str]:
        url = f"{self.host}/api/tags"
        logger.debug("Ollama list_models GET %s", url)
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        logger.debug("Ollama list_models returned %d models: %s", len(models), models)
        return models

    def _stream_chat(
        self,
        model: str,
        messages: list[dict],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        url = f"{self.host}/api/chat"
        payload = {"model": model, "messages": messages, "stream": True}

        parts: list[str] = []
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", url, json=payload) as response:
                logger.debug("Ollama response status=%s", response.status_code)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    body = response.read().decode("utf-8", errors="replace")
                    logger.error(
                        "Ollama HTTP error status=%s body=%s",
                        exc.response.status_code,
                        body[:2000],
                    )
                    raise RuntimeError(self._format_error(body) or str(exc)) from exc
                for line in response.iter_lines():
                    if should_cancel and should_cancel():
                        response.close()
                        raise InterruptedError("Cancelled")
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    chunk = message.get("content", "")
                    if chunk:
                        parts.append(chunk)
                    if data.get("done"):
                        break

        return "".join(parts).strip()

    def complete_text(
        self,
        model: str,
        prompt: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        logger.debug("Ollama complete_text model=%r prompt=%r", model, prompt)
        result = self._stream_chat(
            model,
            [{"role": "user", "content": prompt}],
            should_cancel=should_cancel,
        )
        logger.debug("Ollama complete_text result=%r", result)
        return result

    def extract_field(
        self,
        model: str,
        prompt: str,
        image_png: bytes,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        logger.debug(
            "Ollama extract_field model=%r prompt=%r image_bytes=%d",
            model,
            prompt,
            len(image_png),
        )

        b64 = base64.b64encode(image_png).decode("ascii")
        result = self._stream_chat(
            model,
            [{"role": "user", "content": prompt, "images": [b64]}],
            should_cancel=should_cancel,
        )
        logger.debug("Ollama extract_field result=%r", result)
        return result
