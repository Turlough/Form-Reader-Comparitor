from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

LMSTUDIO_MENU_PREFIX = "lmstudio:"
DEFAULT_HOST = "http://localhost:1234"
DEFAULT_MODELS_DIR = Path.home() / ".lmstudio" / "models"


class LmStudioClient:
    def __init__(
        self,
        host: str | None = None,
        models_dir: Path | None = None,
        timeout: float = 300.0,
    ) -> None:
        resolved = (host or os.environ.get("LMSTUDIO_HOST") or DEFAULT_HOST).strip()
        self.host = resolved.rstrip("/")
        self.models_dir = models_dir or DEFAULT_MODELS_DIR
        self.timeout = timeout
        logger.debug(
            "LmStudioClient initialized host=%s models_dir=%s timeout=%s",
            self.host,
            self.models_dir,
            self.timeout,
        )

    @staticmethod
    def strip_menu_prefix(menu_model: str) -> str | None:
        if menu_model.startswith(LMSTUDIO_MENU_PREFIX):
            return menu_model[len(LMSTUDIO_MENU_PREFIX) :]
        return None

    @staticmethod
    def _is_model_gguf(path: Path) -> bool:
        return not path.stem.lower().startswith("mmproj")

    def _discovered_models(self) -> list[tuple[str, str]]:
        """Return (menu_id, display_label) pairs for downloaded GGUF models."""
        if not self.models_dir.is_dir():
            return []

        entries: list[tuple[str, str]] = []
        for gguf in sorted(self.models_dir.rglob("*.gguf")):
            if not self._is_model_gguf(gguf):
                continue
            rel = gguf.relative_to(self.models_dir).with_suffix("")
            rel_key = rel.as_posix()
            menu_id = f"{LMSTUDIO_MENU_PREFIX}{rel_key}"
            entries.append((menu_id, rel_key))
        return entries

    def list_menu_models(self) -> list[str]:
        models = [menu_id for menu_id, _ in self._discovered_models()]
        logger.debug("Discovered %d LM Studio menu models: %s", len(models), models)
        return models

    def menu_labels(self) -> dict[str, str]:
        return {menu_id: label for menu_id, label in self._discovered_models()}

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

        request_model = Path(api_model).name
        url = f"{self.host}/v1/chat/completions"
        logger.debug(
            "LM Studio extract_field menu_model=%r api_model=%r request_model=%r "
            "prompt=%r image_bytes=%d url=%s",
            api_model,
            api_model,
            request_model,
            prompt,
            len(image_png),
            url,
        )

        b64 = base64.b64encode(image_png).decode("ascii")
        payload = {
            "model": request_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            logger.debug(
                "LM Studio response status=%s body=%s",
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
                    logger.error("LM Studio HTTP error: %s", err or detail)
                except Exception:
                    logger.error("LM Studio HTTP error: %s", detail)
                raise RuntimeError(detail or str(exc)) from exc

            data = response.json()

        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        choices = data.get("choices") or []
        if not choices:
            logger.error("LM Studio returned no choices: %s", data)
            raise RuntimeError("LM Studio returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            result = "".join(parts).strip()
        else:
            result = str(content).strip()
        logger.debug("LM Studio extract_field result=%r", result)
        return result
