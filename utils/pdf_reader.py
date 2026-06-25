from __future__ import annotations

from pathlib import Path


def extract_text_from_pdf(path: Path) -> str:
    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")

    try:
        import fitz

        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8")
        raise RuntimeError(f"PDF extraction failed and no fallback sidecar exists for {path}")
