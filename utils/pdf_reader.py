from __future__ import annotations

from pathlib import Path


def extract_text_from_pdf(path: Path, prefer_sidecar: bool = True) -> str:
    sidecar = path.with_suffix(".txt")
    if prefer_sidecar and sidecar.exists():
        return sidecar.read_text(encoding="utf-8")

    try:
        import fitz

        with fitz.open(path) as doc:
            text = "\n".join(page.get_text() for page in doc).strip()
        if not text:
            raise RuntimeError("PDF extraction completed but returned no text.")
        return text
    except Exception as exc:
        if sidecar.exists():
            return sidecar.read_text(encoding="utf-8")
        raise RuntimeError(
            f"PDF extraction failed for {path.name}. Install PyMuPDF or provide a text-based PDF."
        ) from exc


def refresh_pdf_sidecar(path: Path) -> str:
    text = extract_text_from_pdf(path, prefer_sidecar=False)
    path.with_suffix(".txt").write_text(text, encoding="utf-8")
    return text
