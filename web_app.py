from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from main import DuCOStateMachine
from utils.ocr import refresh_image_sidecar
from utils.pdf_reader import refresh_pdf_sidecar
from utils.security import request_has_valid_token, ui_token_required


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"


class DuCORequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path_only = urlparse(self.path).path
        if not request_has_valid_token(self.path, self.headers):
            self._send_html(_auth_html())
            return
        if path_only == "/" or path_only == "/index.html":
            self._send_html(_index_html(self.path))
            return
        if path_only == "/api/state":
            self._send_json({"ok": True, **_current_state()})
            return
        if path_only.startswith("/outputs/"):
            self._send_output_file(path_only)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        path_only = urlparse(self.path).path
        form = self._read_form() if path_only == "/run" else None
        if not request_has_valid_token(self.path, self.headers, form):
            self.send_error(401, "Valid DUCO_UI_TOKEN required")
            return

        if path_only == "/upload":
            try:
                saved = self._save_uploaded_documents()
                parsed = _refresh_uploaded_sidecars(saved)
                DuCOStateMachine().run()
                token = _token_query(self.path)
                self.send_response(303)
                self.send_header(
                    "Location",
                    f"/{token}&uploaded={len(parsed)}" if token else f"/?uploaded={len(parsed)}",
                )
                self.end_headers()
            except Exception as exc:
                self._send_html(_index_html(self.path, error=str(exc)))
            return

        if path_only == "/run":
            try:
                _update_inputs(form or {})
                DuCOStateMachine().run()
                token = f"?token={form['token']}" if form and form.get("token") else ""
                self.send_response(303)
                self.send_header("Location", f"/{token}")
                self.end_headers()
            except Exception as exc:
                self._send_html(_index_html(self.path, error=str(exc)))
            return

        if path_only != "/api/run":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            _update_inputs(payload)
            final_state = DuCOStateMachine().run()
            self._send_json(
                {
                    "ok": True,
                    "inputs": _input_amounts(),
                    "summary": (OUTPUT_DIR / "summary.txt").read_text(encoding="utf-8"),
                    "report": _read_report(),
                    "run_log": final_state["run_log"],
                }
            )
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        parsed = parse_qs(self.rfile.read(length).decode("utf-8"))
        return {key: values[0] for key, values in parsed.items()}

    def _save_uploaded_documents(self) -> list[Path]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type or "boundary=" not in content_type:
            raise ValueError("Upload form must use multipart/form-data.")

        boundary = content_type.split("boundary=", 1)[1].strip().strip('"').encode("utf-8")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        uploads = _parse_multipart_uploads(body, boundary)
        saved = []

        upload_targets = {
            "priya_invoice_file": ("priya_pt_invoice.png", {".png"}),
            "aarav_mri_file": ("aarav_mri_report.pdf", {".pdf"}),
            "surgeon_estimate_file": ("surgeon_estimate.jpg", {".jpg", ".jpeg"}),
        }
        for field_name, (target_name, allowed_exts) in upload_targets.items():
            upload = uploads.get(field_name)
            if not upload or not upload["content"]:
                continue
            original_ext = Path(str(upload["filename"])).suffix.lower()
            if original_ext not in allowed_exts:
                allowed = ", ".join(sorted(allowed_exts))
                raise ValueError(f"{field_name} must be one of: {allowed}")
            target = DATA_DIR / target_name
            target.write_bytes(upload["content"])
            saved.append(target)
        if not saved:
            raise ValueError("Choose at least one document to upload.")
        return saved

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_output_file(self, request_path: str) -> None:
        relative = unquote(request_path.lstrip("/"))
        path = (ROOT / relative).resolve()
        if not str(path).startswith(str(OUTPUT_DIR.resolve())) or not path.exists():
            self.send_error(404, "Output not found")
            return
        content_type = "text/plain; charset=utf-8"
        if path.suffix == ".svg":
            content_type = "image/svg+xml"
        elif path.suffix == ".png":
            content_type = "image/png"
        elif path.suffix == ".json":
            content_type = "application/json; charset=utf-8"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _current_state() -> dict[str, object]:
    return {
        "inputs": {
            "amounts": _input_amounts(),
            "pt_invoice": (DATA_DIR / "priya_pt_invoice.txt").read_text(encoding="utf-8"),
            "surgeon_estimate": (DATA_DIR / "surgeon_estimate.txt").read_text(encoding="utf-8"),
            "user_query": (DATA_DIR / "user_query.txt").read_text(encoding="utf-8"),
        },
        "summary": _read_text_if_exists(OUTPUT_DIR / "summary.txt"),
        "report": _read_report(),
    }


def _read_report() -> dict[str, object] | None:
    path = OUTPUT_DIR / "final_report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _input_amounts() -> dict[str, int]:
    pt_text = (DATA_DIR / "priya_pt_invoice.txt").read_text(encoding="utf-8")
    estimate_text = (DATA_DIR / "surgeon_estimate.txt").read_text(encoding="utf-8")
    return {
        "pt_amount": _extract_labeled_amount(pt_text, "Total charges", 30000),
        "acl_amount": _extract_cpt_amount(estimate_text, "29888", 350000),
        "meniscus_amount": _extract_cpt_amount(estimate_text, "29881", 100000),
        "surgery_total": _extract_labeled_amount(estimate_text, "Estimated total", 450000),
    }


def _update_inputs(payload: dict[str, object]) -> None:
    amounts = {
        "pt_amount": _amount_from_payload(payload, "pt_amount"),
        "surgery_total": _amount_from_payload(payload, "surgery_total"),
        "acl_amount": _amount_from_payload(payload, "acl_amount"),
        "meniscus_amount": _amount_from_payload(payload, "meniscus_amount"),
    }
    for key, value in amounts.items():
        if value is not None and value <= 0:
            raise ValueError(f"{key} must be a positive INR amount")

    if amounts["pt_amount"] is not None:
        _replace_labeled_amount(DATA_DIR / "priya_pt_invoice.txt", "Total charges", amounts["pt_amount"])
    if amounts["acl_amount"] is not None:
        _replace_cpt_amount(DATA_DIR / "surgeon_estimate.txt", "29888", amounts["acl_amount"])
    if amounts["meniscus_amount"] is not None:
        _replace_cpt_amount(DATA_DIR / "surgeon_estimate.txt", "29881", amounts["meniscus_amount"])
    if amounts["surgery_total"] is not None:
        _replace_labeled_amount(DATA_DIR / "surgeon_estimate.txt", "Estimated total", amounts["surgery_total"])


def _parse_multipart_uploads(body: bytes, boundary: bytes) -> dict[str, dict[str, object]]:
    uploads: dict[str, dict[str, object]] = {}
    for part in body.split(b"--" + boundary):
        part = part.strip()
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_blob, content = part.split(b"\r\n\r\n", 1)
        content = content.rstrip(b"\r\n")
        headers = header_blob.decode("utf-8", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition")), "")
        name = _header_param(disposition, "name")
        filename = _header_param(disposition, "filename")
        if name and filename:
            uploads[name] = {"filename": filename, "content": content}
    return uploads


def _refresh_uploaded_sidecars(paths: list[Path]) -> list[Path]:
    parsed = []
    for path in paths:
        if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            refresh_image_sidecar(path)
        elif path.suffix.lower() == ".pdf":
            refresh_pdf_sidecar(path)
        else:
            raise ValueError(f"Unsupported uploaded file type: {path.name}")
        parsed.append(path.with_suffix(".txt"))
    return parsed


def _header_param(header: str, key: str) -> str:
    match = re.search(rf'{key}="([^"]*)"', header)
    return match.group(1) if match else ""


def _amount_from_payload(payload: dict[str, object], key: str) -> int | None:
    value = str(payload.get(key, "")).strip().replace(",", "")
    if not value:
        return None
    if not value.isdigit():
        raise ValueError(f"{key} must contain digits only")
    return int(value)


def _extract_labeled_amount(text: str, label: str, default: int) -> int:
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else default


def _extract_cpt_amount(text: str, cpt: str, default: int) -> int:
    pattern = rf"CPT\s*{re.escape(cpt)}\s*(?:\(|[-:])\s*.*?(?:\)|[-:])\s*[-:]?\s*(?:INR|Rs\.?|₹)?\s*([0-9,]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else default


def _replace_labeled_amount(path: Path, label: str, amount: int) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(rf"{re.escape(label)}\s*[:\-].*", f"{label}: INR {amount:,}", text, flags=re.IGNORECASE)
    path.write_text(text, encoding="utf-8")


def _replace_cpt_amount(path: Path, cpt: str, amount: int) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = rf"(CPT\s*{re.escape(cpt)}\s*(?:\(|[-:])\s*.*?(?:\)|[-:])\s*[-:]?\s*)(?:INR|Rs\.?|₹)?\s*[0-9,]+"
    text = re.sub(pattern, rf"\1INR {amount:,}", text, flags=re.IGNORECASE)
    path.write_text(text, encoding="utf-8")


def _index_html(path: str = "/", error: str | None = None) -> str:
    state = _current_state()
    if state["report"] is None:
        DuCOStateMachine().run()
        state = _current_state()
    amounts = state["inputs"]["amounts"]
    report = state["report"] or {"cob": {"claims": [], "total_charges_inr": 0, "total_insurer_paid_inr": 0, "household_out_of_pocket_inr": 0}}
    cob = report["cob"]
    token = parse_qs(urlparse(path).query).get("token", [""])[0]
    hidden_token = f'<input type="hidden" name="token" value="{_escape(token)}">' if token else ""
    uploaded = parse_qs(urlparse(path).query).get("uploaded", [""])[0]
    if error:
        status = f"Error: {error}"
    elif uploaded:
        status = f"Uploaded and parsed {uploaded} document(s). Results refreshed from extracted text."
    else:
        status = "Ready. Change values and click Run Analysis."
    status_class = "error" if error else ""
    claims_html = "".join(_claim_card(claim) for claim in cob["claims"])
    upload_action = f"/upload?token={_escape(token)}" if token else "/upload"
    return HTML_TEMPLATE.replace("__PT_AMOUNT__", str(amounts["pt_amount"])).replace(
        "__ACL_AMOUNT__", str(amounts["acl_amount"])
    ).replace("__MENISCUS_AMOUNT__", str(amounts["meniscus_amount"])).replace(
        "__SURGERY_TOTAL__", str(amounts["surgery_total"])
    ).replace("__HIDDEN_TOKEN__", hidden_token).replace("__STATUS_CLASS__", status_class).replace(
        "__STATUS__", _escape(status)
    ).replace("__UPLOAD_ACTION__", upload_action).replace(
        "__DOCUMENT_STATUS__", _document_status_html()
    ).replace("__TOTAL_CHARGES__", _format_inr(cob["total_charges_inr"])).replace(
        "__INSURER_PAID__", _format_inr(cob["total_insurer_paid_inr"])
    ).replace("__PATIENT_PAYS__", _format_inr(cob["household_out_of_pocket_inr"])).replace(
        "__CLAIMS__", claims_html
    ).replace("__SUMMARY__", _escape(str(state["summary"])))


def _auth_html() -> str:
    return """<!doctype html><html><body><h1>DuCO-Agent</h1>
<p>DUCO_UI_TOKEN is enabled. Open the dashboard with <code>?token=your-token</code>.</p>
</body></html>"""


def _token_query(path: str) -> str:
    token = parse_qs(urlparse(path).query).get("token", [""])[0]
    return f"?token={token}" if token else ""


def _document_status_html() -> str:
    files = [
        ("Priya PT invoice", DATA_DIR / "priya_pt_invoice.png", DATA_DIR / "priya_pt_invoice.txt"),
        ("Aarav MRI report", DATA_DIR / "aarav_mri_report.pdf", DATA_DIR / "aarav_mri_report.txt"),
        ("Surgeon estimate", DATA_DIR / "surgeon_estimate.jpg", DATA_DIR / "surgeon_estimate.txt"),
    ]
    rows = []
    for label, path, sidecar in files:
        if path.exists() and sidecar.exists():
            status = "Parsed"
        elif path.exists():
            status = "Uploaded"
        else:
            status = "Missing"
        rows.append(f"<div class=\"doc-status\"><span>{_escape(label)}</span><strong>{status}</strong></div>")
    return "".join(rows)


def _claim_card(claim: dict[str, object]) -> str:
    tag = "Pre-auth required" if claim["preauth_required"] else "No pre-auth"
    return f"""<article class="claim">
<span class="tag">{tag}</span>
<h3>{_escape(str(claim["member_name"]))}</h3>
<div class="row"><span>Service</span><strong>{_escape(str(claim["description"]))}</strong></div>
<div class="row"><span>Charge</span><strong>{_format_inr(int(claim["charge_inr"]))}</strong></div>
<div class="row"><span>Primary</span><strong>{_escape(str(claim["primary_plan_label"]))}</strong></div>
<div class="row"><span>Primary paid</span><strong>{_format_inr(int(claim["primary_paid_inr"]))}</strong></div>
<div class="row"><span>Secondary paid</span><strong>{_format_inr(int(claim["secondary_paid_inr"]))}</strong></div>
<div class="row"><span>Patient</span><strong>{_format_inr(int(claim["patient_paid_inr"]))}</strong></div>
</article>"""


def _format_inr(amount: int) -> str:
    return f"INR {amount:,}"


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DuCO-Agent</title>
<style>
* { box-sizing: border-box; }
:root {
  --bg: #f3f6fb;
  --panel: #ffffff;
  --ink: #142033;
  --muted: #647086;
  --line: #d9e1ee;
  --soft: #f8fafd;
  --brand: #2563eb;
  --brand-dark: #1d4ed8;
  --green: #047857;
  --red: #b91c1c;
  --shadow: 0 16px 42px rgba(30, 41, 59, .10);
}
body { margin: 0; background: var(--bg); color: var(--ink); font-family: Segoe UI, Arial, sans-serif; }
header { padding: 22px 28px; background: var(--panel); border-bottom: 1px solid var(--line); }
.header-inner { max-width: 1380px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; gap: 18px; }
h1 { margin: 0; font-size: 26px; }
.header-pill { border: 1px solid #bfdbfe; background: #eff6ff; color: #1d4ed8; border-radius: 999px; padding: 7px 11px; font-size: 12px; font-weight: 800; white-space: nowrap; }
main { display: grid; grid-template-columns: minmax(330px, 410px) 1fr; gap: 18px; padding: 18px; max-width: 1380px; margin: 0 auto; align-items: start; }
section { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; box-shadow: var(--shadow); overflow: hidden; }
.results { grid-column: 2; grid-row: 1 / span 2; }
.panel-title { padding: 15px 16px; border-bottom: 1px solid var(--line); font-weight: 850; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.panel-body { padding: 16px; }
.sub { color: var(--muted); margin-top: 10px; font-size: 14px; line-height: 1.45; }
label { display: block; font-size: 12px; color: var(--muted); font-weight: 800; margin-bottom: 7px; }
input[type=text], input:not([type]) { width: 100%; height: 42px; border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px; font: inherit; margin-bottom: 13px; background: #fff; transition: border-color .15s ease, box-shadow .15s ease; }
input:focus { outline: none; border-color: #93c5fd; box-shadow: 0 0 0 3px rgba(37, 99, 235, .12); }
button { border: 0; background: var(--brand); color: #fff; padding: 11px 16px; border-radius: 7px; font-weight: 800; cursor: pointer; transition: background .15s ease, transform .12s ease; }
button:hover { background: var(--brand-dark); transform: translateY(-1px); }
button:disabled { opacity: .7; cursor: wait; transform: none; }
button.secondary { width: 100%; margin-top: 4px; }
.status { margin-top: 12px; padding: 10px 12px; border-radius: 7px; border: 1px solid var(--line); color: var(--muted); background: var(--soft); font-size: 13px; font-weight: 750; }
.status.error { color: var(--red); background: #fef2f2; border-color: #fecaca; }
.upload-grid { display: grid; gap: 10px; }
.upload-card { position: relative; display: block; border: 1px dashed #b8c4d8; border-radius: 8px; background: var(--soft); padding: 13px 13px 12px; cursor: pointer; transition: border-color .15s ease, background .15s ease, transform .12s ease; }
.upload-card:hover { border-color: #60a5fa; background: #f0f7ff; transform: translateY(-1px); }
.upload-card input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.upload-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; font-weight: 850; }
.upload-title span:last-child { color: var(--brand); font-size: 12px; }
.upload-help { color: var(--muted); font-size: 12px; margin-top: 5px; }
.file-name { margin-top: 8px; min-height: 18px; color: var(--green); font-size: 12px; font-weight: 800; }
.doc-status { display: flex; justify-content: space-between; gap: 10px; border-top: 1px solid #edf1f6; padding: 8px 0; font-size: 13px; }
.doc-status span { color: var(--muted); }
.doc-status strong { color: var(--green); }
.amount-grid { display: grid; gap: 2px; }
.metrics { display: grid; grid-template-columns: repeat(3, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }
.metric { border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: linear-gradient(180deg, #ffffff, #f8fbff); }
.metric span { display: block; color: var(--muted); font-size: 12px; font-weight: 800; }
.metric strong { display: block; margin-top: 8px; font-size: 23px; }
.claims { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 12px; }
.claim { border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }
.claim h3 { margin: 0 0 12px; font-size: 16px; }
.row { display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid #edf1f6; padding: 9px 0; font-size: 14px; }
.row strong { text-align: right; }
.tag { display: inline-block; padding: 4px 8px; border-radius: 999px; background: #eef6ff; color: #1d4ed8; font-size: 12px; font-weight: 800; margin-bottom: 10px; }
.chart { width: 100%; min-height: 190px; border: 1px solid var(--line); border-radius: 8px; background: #f8fafc; margin-top: 16px; }
.letters { display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 10px; margin-top: 16px; }
.letters a { color: var(--brand); border: 1px solid var(--line); border-radius: 7px; padding: 10px; text-decoration: none; font-weight: 750; background: #fff; transition: border-color .15s ease, background .15s ease; }
.letters a:hover { border-color: #93c5fd; background: #f8fbff; }
pre { margin: 0; white-space: pre-wrap; font-family: Consolas, monospace; font-size: 13px; line-height: 1.45; color: #253044; }
.summary { max-height: 270px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: var(--soft); margin-top: 16px; }
@media (max-width: 900px) {
  .header-inner { align-items: flex-start; flex-direction: column; }
  main, .metrics, .claims, .letters { grid-template-columns: 1fr; }
  .results { grid-column: auto; grid-row: auto; }
}
</style>
</head>
<body>
<header><div class="header-inner"><div><h1>DuCO-Agent Dashboard</h1><div class="sub">Run Coordination of Benefits analysis and review patient-ready outputs.</div></div><div class="header-pill">Local demo workspace</div></div></header>
<main>
<section><div class="panel-title">Optional Document Uploads</div><div class="panel-body">
<form method="post" action="__UPLOAD_ACTION__" enctype="multipart/form-data">
<div class="upload-grid">
<label class="upload-card" for="priyaInvoiceFile"><input id="priyaInvoiceFile" name="priya_invoice_file" type="file" accept=".png,image/png"><div class="upload-title"><span>Priya PT invoice</span><span>PNG</span></div><div class="upload-help">Upload the scanned therapy invoice.</div><div class="file-name" data-file-for="priyaInvoiceFile">No file selected</div></label>
<label class="upload-card" for="aaravMriFile"><input id="aaravMriFile" name="aarav_mri_file" type="file" accept=".pdf,application/pdf"><div class="upload-title"><span>Aarav MRI report</span><span>PDF</span></div><div class="upload-help">Upload the radiology report used for clinical evidence.</div><div class="file-name" data-file-for="aaravMriFile">No file selected</div></label>
<label class="upload-card" for="surgeonEstimateFile"><input id="surgeonEstimateFile" name="surgeon_estimate_file" type="file" accept=".jpg,.jpeg,image/jpeg"><div class="upload-title"><span>Surgeon estimate</span><span>JPG</span></div><div class="upload-help">Upload the billing sheet with CPT lines and amounts.</div><div class="file-name" data-file-for="surgeonEstimateFile">No file selected</div></label>
</div>
<button class="secondary" type="submit">Upload Documents</button>
</form>
<div class="sub">Use this only when you want to parse fresh files. You can skip uploads and run the amount inputs below directly.</div>
__DOCUMENT_STATUS__
</div></section>
<section><div class="panel-title">Manual Amount Analysis</div><div class="panel-body">
<form method="post" action="/run">
__HIDDEN_TOKEN__
<div class="amount-grid">
<label for="ptAmount">Priya PT bill</label><input id="ptAmount" name="pt_amount" inputmode="numeric" value="__PT_AMOUNT__">
<label for="aclAmount">Aarav ACL reconstruction CPT 29888</label><input id="aclAmount" name="acl_amount" inputmode="numeric" value="__ACL_AMOUNT__">
<label for="meniscusAmount">Aarav meniscectomy CPT 29881</label><input id="meniscusAmount" name="meniscus_amount" inputmode="numeric" value="__MENISCUS_AMOUNT__">
<label for="surgeryTotal">Aarav surgery estimated total</label><input id="surgeryTotal" name="surgery_total" inputmode="numeric" value="__SURGERY_TOTAL__">
</div>
<button class="secondary" type="submit">Run Analysis</button>
</form>
<div class="sub">This works without uploading documents. The server updates the extracted text values, reruns all agents, and reloads this page.</div>
<div class="status __STATUS_CLASS__">__STATUS__</div>
</div></section>
<section class="results"><div class="panel-title">Results</div><div class="panel-body">
<div class="metrics">
<div class="metric"><span>Total Charges</span><strong>__TOTAL_CHARGES__</strong></div>
<div class="metric"><span>Insurer Paid</span><strong>__INSURER_PAID__</strong></div>
<div class="metric"><span>Patient Pays</span><strong>__PATIENT_PAYS__</strong></div>
</div>
<div class="claims">__CLAIMS__</div>
<img class="chart" src="/outputs/charts/cost_flow.svg" alt="COB cost flow chart">
<div class="letters">
<a href="/outputs/preauth_letters/aarav_plan_b_primary_preauth.txt" download="aarav_plan_b_primary_preauth.txt">Download Aarav Plan B Letter</a>
<a href="/outputs/preauth_letters/aarav_plan_a_secondary_preauth.txt" download="aarav_plan_a_secondary_preauth.txt">Download Aarav Plan A Letter</a>
<a href="/outputs/preauth_letters/priya_pt_claim_cover_letter.txt" download="priya_pt_claim_cover_letter.txt">Download Priya PT Letter</a>
</div>
<div class="summary"><pre>__SUMMARY__</pre></div>
</div></section>
</main>
<script>
document.querySelectorAll('input[type="file"]').forEach(input => {
  input.addEventListener('change', () => {
    const target = document.querySelector(`[data-file-for="${input.id}"]`);
    if (!target) return;
    target.textContent = input.files && input.files.length ? input.files[0].name : 'No file selected';
  });
});
document.querySelectorAll('form').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
      button.textContent = button.textContent.includes('Upload') ? 'Uploading...' : 'Running...';
    }
  });
});
</script>
</body>
</html>"""

def main() -> None:
    mode = "token protected" if ui_token_required() else "local demo"
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DuCORequestHandler)
    print(f"DuCO-Agent UI running at http://0.0.0.0:{port} ({mode})")
    server.serve_forever()


if __name__ == "__main__":
    main()

