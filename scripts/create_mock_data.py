from __future__ import annotations

import base64
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

INVOICE_TEXT = """Sen Rehabilitation Clinic
Patient: Priya Sen
Service: Physical Therapy Evaluation and Therapeutic Exercise
Dates of service: 03-Jun-2026, 06-Jun-2026, 10-Jun-2026, 13-Jun-2026
Billing note: chronic back pain program, submit to primary then COB secondary.
Total charges: INR 30,000
"""

MRI_TEXT = """Mumbai Sports Imaging Centre
Patient: Aarav Sen
MRI Right Knee
Findings: Complete tear of the anterior cruciate ligament (ACL). Associated medial meniscus tear.
Impression: Complete ACL tear with medial meniscus tear. Orthopedic surgical correlation advised.
"""

ESTIMATE_TEXT = """Mumbai Orthopedic Surgery Associates
Patient: Aarav Sen
CPT 29888 - Arthroscopically aided ACL reconstruction - INR 3,50,000
CPT 29881 - Arthroscopy, knee, surgical; with meniscectomy - INR 1,00,000
Estimated total: INR 4,50,000
"""

QUERY_TEXT = """Hi DuCO-Agent, I need to get my knee operated on soon, and Priya has some physical therapy bills lying around. We have Insurer1 (Plan A) and Insurer2 (Plan B). Can you help us figure out which plan pays first for my surgery and her bills? How much will we actually have to pay out of our own pocket? Also, we need the pre-auth letters generated for both insurers so we don't end up with a claim rejection. Please help!"""

ONE_BY_ONE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/axuWn8AAAAASUVORK5CYII="
)


def main() -> None:
    DATA.mkdir(exist_ok=True)
    _write_text_sidecars()
    _write_images()
    _write_pdf()
    print(f"Mock files written to {DATA}")


def _write_text_sidecars() -> None:
    (DATA / "priya_pt_invoice.txt").write_text(INVOICE_TEXT, encoding="utf-8")
    (DATA / "aarav_mri_report.txt").write_text(MRI_TEXT, encoding="utf-8")
    (DATA / "surgeon_estimate.txt").write_text(ESTIMATE_TEXT, encoding="utf-8")
    (DATA / "user_query.txt").write_text(QUERY_TEXT, encoding="utf-8")


def _write_images() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont

        _text_image(DATA / "priya_pt_invoice.png", INVOICE_TEXT, "RGB", (248, 246, 239))
        _text_image(DATA / "surgeon_estimate.jpg", ESTIMATE_TEXT, "RGB", (245, 248, 252))
    except Exception:
        (DATA / "priya_pt_invoice.png").write_bytes(ONE_BY_ONE_PNG)
        (DATA / "surgeon_estimate.jpg").write_bytes(ONE_BY_ONE_PNG)


def _text_image(path: Path, text: str, mode: str, bg: tuple[int, int, int]) -> None:
    from PIL import Image, ImageDraw

    image = Image.new(mode, (1100, 620), bg)
    draw = ImageDraw.Draw(image)
    y = 42
    for line in text.splitlines():
        draw.text((52, y), line, fill=(28, 35, 45))
        y += 42
    image.save(path)


def _write_pdf() -> None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        path = DATA / "aarav_mri_report.pdf"
        c = canvas.Canvas(str(path), pagesize=letter)
        y = 740
        for line in MRI_TEXT.splitlines():
            c.drawString(72, y, line)
            y -= 24
        c.save()
    except Exception:
        (DATA / "aarav_mri_report.pdf").write_bytes(_minimal_pdf(MRI_TEXT))


def _minimal_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 740 Td ({escaped[:900]}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1"))
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref}\n%%EOF\n"
    return pdf.encode("latin-1")


if __name__ == "__main__":
    main()
