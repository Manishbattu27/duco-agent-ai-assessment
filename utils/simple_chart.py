from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any


def write_cost_flow_chart(claims: list[dict[str, Any]], output_dir: Path) -> list[str]:
    svg_path = output_dir / "cost_flow.svg"
    png_path = output_dir / "cost_flow.png"
    try:
        _write_matplotlib_png(claims, png_path)
    except Exception:
        png_path.write_bytes(_fallback_png(claims))
    svg_path.write_text(_svg(claims), encoding="utf-8")
    return [str(svg_path), str(png_path)]


def _write_matplotlib_png(claims: list[dict[str, Any]], png_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    labels = [claim["claim_id"] for claim in claims]
    primary = [claim["primary_paid_inr"] for claim in claims]
    secondary = [claim["secondary_paid_inr"] for claim in claims]
    patient = [claim["patient_paid_inr"] for claim in claims]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(labels, primary, label="Primary insurer")
    ax.bar(labels, secondary, bottom=primary, label="Secondary insurer")
    bottoms = [p + s for p, s in zip(primary, secondary)]
    ax.bar(labels, patient, bottom=bottoms, label="Patient")
    ax.set_ylabel("INR")
    ax.set_title("DuCO-Agent COB Cost Flow")
    ax.legend()
    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)


def _svg(claims: list[dict[str, Any]]) -> str:
    max_charge = max(claim["charge_inr"] for claim in claims)
    rows = []
    y = 70
    colors = {
        "primary_paid_inr": "#2563eb",
        "secondary_paid_inr": "#059669",
        "patient_paid_inr": "#dc2626",
    }
    labels = {
        "primary_paid_inr": "Primary",
        "secondary_paid_inr": "Secondary",
        "patient_paid_inr": "Patient",
    }
    for claim in claims:
        rows.append(f'<text x="30" y="{y - 12}" font-size="15" font-family="Arial">{claim["claim_id"]}</text>')
        x = 190
        for key in ("primary_paid_inr", "secondary_paid_inr", "patient_paid_inr"):
            width = max(1, int((claim[key] / max_charge) * 520))
            rows.append(
                f'<rect x="{x}" y="{y - 30}" width="{width}" height="24" fill="{colors[key]}" rx="3"/>'
            )
            if width > 75:
                rows.append(
                    f'<text x="{x + 8}" y="{y - 13}" fill="white" font-size="12" font-family="Arial">'
                    f'{labels[key]} INR {claim[key]:,}</text>'
                )
            x += width
        rows.append(
            f'<text x="190" y="{y + 12}" font-size="12" font-family="Arial" fill="#374151">'
            f'Total charge INR {claim["charge_inr"]:,}</text>'
        )
        y += 90
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="850" height="{y + 40}" viewBox="0 0 850 {y + 40}">
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="30" y="35" font-size="22" font-family="Arial" font-weight="700" fill="#111827">DuCO-Agent COB Cost Flow</text>
{''.join(rows)}
</svg>
"""


def _fallback_png(claims: list[dict[str, Any]]) -> bytes:
    width = 850
    height = 80 + (len(claims) * 90)
    pixels = bytearray([248, 250, 252] * width * height)
    colors = {
        "primary_paid_inr": (37, 99, 235),
        "secondary_paid_inr": (5, 150, 105),
        "patient_paid_inr": (220, 38, 38),
    }
    max_charge = max(claim["charge_inr"] for claim in claims)

    y = 55
    for claim in claims:
        x = 190
        for key in ("primary_paid_inr", "secondary_paid_inr", "patient_paid_inr"):
            bar_width = max(1, int((claim[key] / max_charge) * 520))
            _rect(pixels, width, height, x, y, bar_width, 26, colors[key])
            x += bar_width
        y += 90
    return _png_bytes(width, height, pixels)


def _rect(
    pixels: bytearray,
    canvas_width: int,
    canvas_height: int,
    x: int,
    y: int,
    width: int,
    height: int,
    color: tuple[int, int, int],
) -> None:
    for row in range(max(0, y), min(canvas_height, y + height)):
        for col in range(max(0, x), min(canvas_width, x + width)):
            idx = (row * canvas_width + col) * 3
            pixels[idx : idx + 3] = bytes(color)


def _png_bytes(width: int, height: int, rgb: bytearray) -> bytes:
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(rgb[y * stride : (y + 1) * stride])

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
