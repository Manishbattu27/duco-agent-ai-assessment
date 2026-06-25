from __future__ import annotations

from pathlib import Path


def extract_text_from_image(path: Path) -> str:
    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")

    try:
        from PIL import Image
        import pytesseract

        return pytesseract.image_to_string(Image.open(path))
    except Exception:
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8")
        raise RuntimeError(f"OCR failed and no fallback sidecar exists for {path}")
