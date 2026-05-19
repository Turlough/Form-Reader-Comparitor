from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from .image_loader import crop_normalized_rectangle

if TYPE_CHECKING:
    from paddleocr import PaddleOCR

OCR_ENGINE_PADDLE = "paddle"
OCR_ENGINE_TESSERACT = "tesseract"
DEFAULT_OCR_ENGINE = OCR_ENGINE_PADDLE

OCR_MENU_ENGINES: list[tuple[str, str]] = [
    ("Paddle", OCR_ENGINE_PADDLE),
    ("Tesseract", OCR_ENGINE_TESSERACT),
]

_TESSERACT_WINDOWS_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def _resolve_tesseract_cmd() -> str:
    env_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if env_cmd:
        return env_cmd

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    for candidate in _TESSERACT_WINDOWS_CANDIDATES:
        if candidate.is_file():
            return str(candidate)

    return "tesseract"


class OcrService:
    def __init__(self) -> None:
        self._paddle: PaddleOCR | None = None

    def read_region(
        self,
        engine: str,
        image: Image.Image,
        rectangle: list[float],
    ) -> str:
        crop = crop_normalized_rectangle(image, rectangle)
        if engine == OCR_ENGINE_PADDLE:
            return self._read_paddle(crop)
        if engine == OCR_ENGINE_TESSERACT:
            return self._read_tesseract(crop)
        raise ValueError(f"Unknown OCR engine: {engine}")

    def _get_paddle(self) -> PaddleOCR:
        if self._paddle is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install with: pip install paddleocr paddlepaddle"
                ) from exc
            # PaddleOCR 3.x: show_log/use_angle_cls removed; enable_mkldnn=False avoids
            # a Paddle 3.3+ CPU oneDNN bug on Windows.
            self._paddle = PaddleOCR(
                lang="en",
                use_textline_orientation=True,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                enable_mkldnn=False,
            )
        return self._paddle

    def _read_tesseract(self, image: Image.Image) -> str:
        try:
            import pytesseract
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract is not installed. Install with: pip install pytesseract"
            ) from exc
        pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract_cmd()
        try:
            return pytesseract.image_to_string(image).strip()
        except pytesseract.TesseractNotFoundError as exc:
            cmd = pytesseract.pytesseract.tesseract_cmd
            raise RuntimeError(
                f"Tesseract executable not found (tried: {cmd!r}). "
                "Install from https://github.com/tesseract-ocr/tesseract, "
                "add it to PATH, or set TESSERACT_CMD to the full path of tesseract.exe"
            ) from exc

    def _read_paddle(self, image: Image.Image) -> str:
        import numpy as np

        ocr = self._get_paddle()
        arr = np.array(image.convert("RGB"))
        result = ocr.ocr(arr)
        return _paddle_result_to_text(result)


def _paddle_result_to_text(result) -> str:
    if not result:
        return ""
    page = result[0]
    if page is None:
        return ""
    rec_texts = page.get("rec_texts") if isinstance(page, dict) else getattr(page, "rec_texts", None)
    if rec_texts:
        return " ".join(str(t) for t in rec_texts).strip()
    parts: list[str] = []
    for line in page:
        if not isinstance(line, (list, tuple)) or len(line) < 2:
            continue
        text_part = line[1]
        if isinstance(text_part, (list, tuple)) and text_part:
            parts.append(str(text_part[0]))
        elif isinstance(text_part, str):
            parts.append(text_part)
    return " ".join(parts).strip()
