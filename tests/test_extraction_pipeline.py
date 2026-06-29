import sys
import types
import uuid
from pathlib import Path

import fitz
from PIL import Image

from utils.ocr import refresh_image_sidecar
from utils.pdf_reader import refresh_pdf_sidecar
from web_app import _refresh_uploaded_sidecars


def _runtime_dir(name: str) -> Path:
    path = Path(".test_runtime") / f"{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_image_refresh_uses_ocr_not_existing_sidecar(monkeypatch):
    runtime_dir = _runtime_dir("image_refresh")
    image_path = runtime_dir / "invoice.png"
    sidecar_path = runtime_dir / "invoice.txt"
    Image.new("RGB", (120, 80), "white").save(image_path)
    sidecar_path.write_text("old sidecar text", encoding="utf-8")

    fake_pytesseract = types.SimpleNamespace(image_to_string=lambda _image: "Total charges: INR 47,500")
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    text = refresh_image_sidecar(image_path)

    assert text == "Total charges: INR 47,500"
    assert sidecar_path.read_text(encoding="utf-8") == "Total charges: INR 47,500"


def test_pdf_refresh_extracts_text_without_existing_sidecar():
    runtime_dir = _runtime_dir("pdf_refresh")
    pdf_path = runtime_dir / "mri.pdf"
    sidecar_path = runtime_dir / "mri.txt"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Complete tear of the anterior cruciate ligament ACL")
    doc.save(pdf_path)
    doc.close()

    text = refresh_pdf_sidecar(pdf_path)

    assert "ACL" in text
    assert "anterior cruciate ligament" in sidecar_path.read_text(encoding="utf-8")


def test_upload_refresh_creates_sidecars_for_png_jpg_and_pdf(monkeypatch):
    runtime_dir = _runtime_dir("upload_refresh")
    invoice_path = runtime_dir / "priya_pt_invoice.png"
    estimate_path = runtime_dir / "surgeon_estimate.jpg"
    mri_path = runtime_dir / "aarav_mri_report.pdf"
    Image.new("RGB", (120, 80), "white").save(invoice_path)
    Image.new("RGB", (120, 80), "white").save(estimate_path)

    fake_pytesseract = types.SimpleNamespace(
        image_to_string=lambda image: (
            "CPT 29888 (ACL reconstruction) - INR 4,20,000"
            if image.format == "JPEG"
            else "Total charges: INR 47,500"
        )
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Complete tear of the anterior cruciate ligament ACL")
    doc.save(mri_path)
    doc.close()

    sidecars = _refresh_uploaded_sidecars([invoice_path, estimate_path, mri_path])

    assert len(sidecars) == 3
    assert "47,500" in invoice_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert "29888" in estimate_path.with_suffix(".txt").read_text(encoding="utf-8")
    assert "ACL" in mri_path.with_suffix(".txt").read_text(encoding="utf-8")
