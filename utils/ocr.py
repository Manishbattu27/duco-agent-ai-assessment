from __future__ import annotations

from pathlib import Path

from utils.llm import optional_vision_text_extraction


COMMON_TESSERACT_PATHS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def extract_text_from_image(path: Path, prefer_sidecar: bool = True) -> str:
    sidecar = path.with_suffix(".txt")
    if prefer_sidecar and sidecar.exists():
        return sidecar.read_text(encoding="utf-8")

    ocr_error: Exception | None = None
    try:
        from PIL import Image
        import pytesseract

        _configure_tesseract(pytesseract)
        text = pytesseract.image_to_string(Image.open(path)).strip()
        if not text:
            raise RuntimeError("OCR completed but returned no text.")
        return text
    except Exception as exc:
        ocr_error = exc

    vision_text = optional_vision_text_extraction(path, document_type=path.stem.replace("_", " "))
    if vision_text:
        return vision_text

    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")
    if ocr_error:
        raise RuntimeError(
            f"OCR failed for {path.name}. Install Pillow, pytesseract, and the Tesseract OCR engine, "
            "configure Gemini Vision OCR, or provide a readable image."
        ) from ocr_error
    raise RuntimeError(f"OCR failed for {path.name}.")


def refresh_image_sidecar(path: Path) -> str:
    text = extract_text_from_image(path, prefer_sidecar=False)
    path.with_suffix(".txt").write_text(text, encoding="utf-8")
    return text


def _configure_tesseract(pytesseract_module: object) -> None:
    for candidate in COMMON_TESSERACT_PATHS:
        if candidate.exists():
            command_holder = getattr(pytesseract_module, "pytesseract", None)
            if command_holder is not None:
                command_holder.tesseract_cmd = str(candidate)
            return
