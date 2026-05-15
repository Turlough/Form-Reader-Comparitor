from __future__ import annotations

import base64
import json
from typing import Callable

import httpx

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "glm-ocr"


class OllamaClient:
    def __init__(self, host: str = DEFAULT_HOST, timeout: float = 300.0) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[str]:
        response = httpx.get(f"{self.host}/api/tags", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]

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

        b64 = base64.b64encode(image_png).decode("ascii")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
            "stream": True,
        }

        parts: list[str] = []
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream(
                "POST",
                f"{self.host}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
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
