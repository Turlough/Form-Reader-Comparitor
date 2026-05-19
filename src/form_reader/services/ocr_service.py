from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from .image_loader import crop_normalized_rectangle

if TYPE_CHECKING:
    from paddleocr import PaddleOCR

OCR_ENGINE_PADDLE = "paddle"
DEFAULT_OCR_ENGINE = OCR_ENGINE_PADDLE

OCR_MENU_ENGINES: list[tuple[str, str]] = [
    ("Paddle", OCR_ENGINE_PADDLE),
]


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
