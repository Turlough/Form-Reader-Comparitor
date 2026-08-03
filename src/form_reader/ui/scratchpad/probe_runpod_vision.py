#!/usr/bin/env python3
"""Vision RunPod chat probe. Same payload shape as RunPodClient.

Usage:
  uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py
  uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --large
  uv run python src/form_reader/ui/scratchpad/probe_runpod_vision.py --image /path/to.png
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageDraw

# 1x1 PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _load_dotenv() -> Path | None:
    here = Path(__file__).resolve().parent
    for d in [here, *here.parents]:
        candidate = d / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return candidate
    load_dotenv()
    return None


def _large_form_png() -> bytes:
    img = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), "SURNAME: SMITH", fill="black")
    draw.text((40, 80), "NAME: JOHN", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--large",
        action="store_true",
        help="Send a ~form-page PNG (1200x1600) instead of a 1x1 pixel",
    )
    parser.add_argument("--image", type=Path, help="PNG/JPEG file to send")
    parser.add_argument("--max-tokens", type=int, default=None)
    args = parser.parse_args()

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

    if args.image:
        png = args.image.read_bytes()
        mime = "image/jpeg" if args.image.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    elif args.large:
        png = _large_form_png()
        mime = "image/png"
    else:
        png = _TINY_PNG
        mime = "image/png"

    b64 = base64.b64encode(png).decode("ascii")
    url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1/chat/completions"
    payload: dict = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What are the Surname and Name? Reply only the values.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
    }
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens

    print(f"POST {url}", file=sys.stderr)
    print(f"model={model!r} image_bytes={len(png)} mime={mime}", file=sys.stderr)

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
