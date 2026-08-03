#!/usr/bin/env python3
"""Text-only RunPod chat probe (no image). Loads repo-root .env."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


def _load_dotenv() -> Path | None:
    here = Path(__file__).resolve().parent
    for d in [here, *here.parents]:
        candidate = d / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return candidate
    load_dotenv()
    return None


def main() -> int:
    env_path = _load_dotenv()
    api_key = os.environ.get("RUNPOD_API_KEY", "").strip()
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "").strip()
    model = os.environ.get("RUNPOD_MODEL", "").strip()

    if env_path:
        print(f"Loaded .env from {env_path}", file=sys.stderr)
    else:
        print("No .env found; using process environment", file=sys.stderr)

    missing = [
        name
        for name, value in (
            ("RUNPOD_API_KEY", api_key),
            ("RUNPOD_ENDPOINT_ID", endpoint_id),
            ("RUNPOD_MODEL", model),
        )
        if not value
    ]
    if missing:
        print(f"Missing: {', '.join(missing)}", file=sys.stderr)
        return 1

    url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hi"}],
    }
    print(f"POST {url}", file=sys.stderr)
    print(f"model={model!r}", file=sys.stderr)

    with httpx.Client(timeout=600.0) as client:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    print(f"status={response.status_code}", file=sys.stderr)
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
