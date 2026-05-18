from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PyQt6.QtGui import QImage

_PLACEHOLDER_SIZE = (720, 360)
# Keep display decode bounded so import does not hang/OOM on large scans.
_MAX_DISPLAY_PIXELS = 12_000_000


def load_first_page_image(path: Path) -> Image.Image | None:
    """Load the first page as an RGB PIL image.

    Returns ``None`` if the file cannot be located. Raises ``OSError`` /
    ``ValueError`` (from Pillow / PyMuPDF) on decode failure so callers can
    surface a useful diagnostic instead of a generic placeholder.
    """
    resolved = _resolve_case_insensitive(path)
    if resolved is None:
        return None
    suffix = resolved.suffix.lower()
    if suffix == ".pdf":
        image = _load_pdf_first_page(resolved)
    else:
        image = _load_raster(resolved)
    return _limit_image_size(image)


def _resolve_case_insensitive(path: Path) -> Path | None:
    """Return ``path`` if it exists, otherwise try a case-insensitive lookup.

    Windows-produced EXPORT.TXT files often use a different filename case than the
    actual files on a Linux filesystem (e.g. ``SCAN001.TIF`` vs ``scan001.tif``).
    Walk the path components, matching each one case-insensitively against the
    real directory entries.
    """
    if path.is_file():
        return path

    if path.is_absolute():
        current = Path(path.anchor)
        parts = path.relative_to(current).parts
    else:
        current = Path()
        parts = path.parts

    for part in parts:
        probe = current / part
        if probe.exists():
            current = probe
            continue
        search_dir = current if str(current) else Path(".")
        try:
            entries = list(search_dir.iterdir())
        except (FileNotFoundError, NotADirectoryError, PermissionError):
            return None
        lowered = part.lower()
        match = next((entry for entry in entries if entry.name.lower() == lowered), None)
        if match is None:
            return None
        current = match

    return current if current.is_file() else None


def pil_to_qimage(image: Image.Image) -> QImage:
    """Convert PIL to QImage without ImageQt (avoids Windows segfaults)."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    bytes_per_line = 3 * width
    qimage = QImage(
        rgb.tobytes(),
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888,
    )
    return qimage.copy()


def _limit_image_size(
    image: Image.Image,
    max_pixels: int = _MAX_DISPLAY_PIXELS,
) -> Image.Image:
    width, height = image.size
    if width * height <= max_pixels:
        return image
    scale = (max_pixels / (width * height)) ** 0.5
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _load_pdf_first_page(path: Path) -> Image.Image:
    import fitz

    doc = fitz.open(path)
    try:
        page = doc[0]
        rect = page.rect
        area = max(rect.width * rect.height, 1.0)
        zoom = min(2.0, (_MAX_DISPLAY_PIXELS / area) ** 0.5)
        zoom = max(0.75, zoom)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def _load_raster(path: Path) -> Image.Image:
    """Open a raster and return its first frame as a fully-detached RGB image.

    Multi-page scanned TIFFs are common here and can use modes such as ``1``
    (CCITT G4 bilevel), ``L``, ``P``, ``I;16`` or ``CMYK``. We force a load
    while the source file is still open, then convert to RGB so the returned
    image is safe to use after the file handle is closed.
    """
    with Image.open(path) as img:
        if getattr(img, "n_frames", 1) > 1:
            img.seek(0)
        img.load()
        if img.mode == "RGB":
            return img.copy()
        return img.convert("RGB")


def placeholder_image(message: str = "Image not found") -> Image.Image:
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", _PLACEHOLDER_SIZE, color=(220, 220, 220))
    draw = ImageDraw.Draw(img)
    draw.multiline_text((20, 20), message, fill=(80, 80, 80))
    return img


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
