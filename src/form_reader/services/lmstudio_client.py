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

    def list_loaded_models(self) -> list[str]:
        url = f"{self.host}/v1/models"
        logger.debug("LM Studio list_loaded_models GET %s", url)
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        models = [m["id"] for m in data.get("data", []) if m.get("id")]
        logger.debug("LM Studio loaded models: %s", models)
        return models

    @staticmethod
    def _base_model_id(model_id: str) -> str:
        if ":" in model_id:
            base, suffix = model_id.rsplit(":", 1)
            if suffix.isdigit():
                return base
        return model_id

    @staticmethod
    def _normalize_model_key(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _loaded_model_keys(self, model_id: str) -> set[str]:
        keys = {self._normalize_model_key(model_id)}
        base = self._base_model_id(model_id)
        keys.add(self._normalize_model_key(base))
        if "@" in base:
            keys.add(self._normalize_model_key(base.split("@", 1)[0]))
        if "/" in base:
            keys.add(self._normalize_model_key(base.rsplit("/", 1)[-1]))
        return keys

    def resolve_request_model(self, api_model: str, loaded: list[str] | None = None) -> str:
        """Map a downloaded GGUF path to a loaded LM Studio model id."""
        loaded = loaded if loaded is not None else self.list_loaded_models()
        if not loaded:
            raise RuntimeError("No models are loaded in LM Studio.")

        rel_path = Path(api_model)
        filename_stem = rel_path.name
        path_parts = list(rel_path.parts)
        search_keys = {self._normalize_model_key(filename_stem)}
        if rel_path.parent.name:
            search_keys.add(self._normalize_model_key(rel_path.parent.name))
        for part in path_parts:
            search_keys.add(self._normalize_model_key(part))

        matches: list[str] = []
        for model_id in loaded:
            model_keys = self._loaded_model_keys(model_id)
            if model_keys & search_keys:
                matches.append(model_id)
                continue

            base = self._base_model_id(model_id)
            filename_key = self._normalize_model_key(filename_stem)
            base_key = self._normalize_model_key(base.rsplit("@", 1)[0].rsplit("/", 1)[-1])
            if base_key and (
                filename_key.startswith(base_key)
                or base_key in filename_key
                or any(base_key in part_key for part_key in search_keys)
            ):
                matches.append(model_id)

        if not matches:
            raise RuntimeError(
                f"No loaded LM Studio model matches {api_model!r}. "
                f"Loaded models: {', '.join(loaded)}"
            )

        unique = list(dict.fromkeys(matches))
        primary = [m for m in unique if m == self._base_model_id(m)]
        resolved = primary[0] if primary else unique[0]
        logger.debug(
            "Resolved LM Studio model api_model=%r -> request_model=%r (loaded=%s)",
            api_model,
            resolved,
            loaded,
        )
        return resolved

    def _chat_completion(
        self,
        api_model: str,
        messages: list[dict],
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        request_model = self.resolve_request_model(api_model)
        url = f"{self.host}/v1/chat/completions"
        payload = {"model": request_model, "messages": messages}

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
            return "".join(parts).strip()
        return str(content).strip()

    def complete_text(
        self,
        api_model: str,
        prompt: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        if should_cancel and should_cancel():
            raise InterruptedError("Cancelled")

        logger.debug("LM Studio complete_text api_model=%r prompt=%r", api_model, prompt)
        result = self._chat_completion(
            api_model,
            [{"role": "user", "content": prompt}],
            should_cancel=should_cancel,
        )
        logger.debug("LM Studio complete_text result=%r", result)
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
            "LM Studio extract_field api_model=%r prompt=%r image_bytes=%d",
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
        logger.debug("LM Studio extract_field result=%r", result)
        return result
