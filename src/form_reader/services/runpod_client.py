from __future__ import annotations

import base64
import logging
import os
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

RUNPOD_MENU_PREFIX = "runpod:"
DEFAULT_TIMEOUT = 600.0


class RunPodClient:
    """OpenAI-compatible RunPod serverless vLLM client (static .env config)."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_id: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else os.environ.get("RUNPOD_API_KEY", "")
        ).strip()
        self.endpoint_id = (
            endpoint_id
            if endpoint_id is not None
            else os.environ.get("RUNPOD_ENDPOINT_ID", "")
        ).strip()
        self.model = (
            model if model is not None else os.environ.get("RUNPOD_MODEL", "")
        ).strip()
        self.timeout = timeout
        logger.debug(
            "RunPodClient initialized configured=%s endpoint_id=%s model=%s timeout=%s",
            self.is_configured,
            self.endpoint_id or "(unset)",
            self.model or "(unset)",
            self.timeout,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.endpoint_id and self.model)

    @property
    def base_url(self) -> str:
        return f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1"

    def list_menu_models(self) -> list[str]:
        if not self.is_configured:
            return []
        return [f"{RUNPOD_MENU_PREFIX}{self.model}"]

    def menu_labels(self) -> dict[str, str]:
        if not self.is_configured:
            return {}
        menu_id = f"{RUNPOD_MENU_PREFIX}{self.model}"
        return {menu_id: self.model}

    def missing_config_hint(self) -> str:
        missing: list[str] = []
        if not self.api_key:
            missing.append("RUNPOD_API_KEY")
        if not self.endpoint_id:
            missing.append("RUNPOD_ENDPOINT_ID")
        if not self.model:
            missing.append("RUNPOD_MODEL")
        if not missing:
            return ""
        return f"(set {', '.join(missing)} in .env)"

    @staticmethod
    def strip_menu_prefix(menu_model: str) -> str | None:
        if menu_model.startswith(RUNPOD_MENU_PREFIX):
            return menu_model[len(RUNPOD_MENU_PREFIX) :]
        return None

    def _chat_completion(
        self,
        api_model: str,
        messages: list[dict],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if not self.is_configured:
            raise RuntimeError(
                "RunPod is not configured "
                "(set RUNPOD_API_KEY, RUNPOD_ENDPOINT_ID, and RUNPOD_MODEL)."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": api_model, "messages": messages}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            logger.debug(
                "RunPod response status=%s body=%s",
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
                    if isinstance(err, dict):
                        detail = err.get("message", detail)
                    else:
                        detail = str(err) or detail
                    logger.error("RunPod HTTP error: %s", err or detail)
                except Exception:
                    logger.error("RunPod HTTP error: %s", detail)
                raise RuntimeError(detail or str(exc)) from exc

            data = response.json()

        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        choices = data.get("choices") or []
        if not choices:
            logger.error("RunPod returned no choices: %s", data)
            raise RuntimeError("RunPod returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return "".join(parts).strip()
        return str(content).strip()

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
            "RunPod extract_field api_model=%r prompt=%r image_bytes=%d",
            api_model,
            prompt,
            len(image_png),
        )

        b64 = base64.b64encode(image_png).decode("ascii")
        result = self._chat_completion(
            api_model,
            [
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
            should_cancel=should_cancel,
        )
        logger.debug("RunPod extract_field result=%r", result)
        return result
