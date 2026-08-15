#!/usr/bin/env python3
"""Text-only RunPod chat probe (no image). Loads repo-root .env."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from form_reader.services.runpod_client import RunPodClient


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
    client = RunPodClient()

    if env_path:
        print(f"Loaded .env from {env_path}", file=sys.stderr)
    else:
        print("No .env found; using process environment", file=sys.stderr)

    if not client.is_configured:
        print(f"Missing: {client.missing_config_hint()}", file=sys.stderr)
        return 1

    url = f"{client.base_url}/chat/completions"
    payload = {
        "model": client.model,
        "messages": [{"role": "user", "content": "Say hi"}],
    }
    print(f"POST {url}", file=sys.stderr)
    print(f"model={client.model!r}", file=sys.stderr)

    with httpx.Client(timeout=600.0) as http:
        response = http.post(url, headers=client.request_headers, json=payload)

    print(f"status={response.status_code}", file=sys.stderr)
    try:
        data = response.json()
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError:
        print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
