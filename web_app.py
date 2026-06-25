from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from main import DuCOStateMachine


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"


class DuCORequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path_only = urlparse(self.path).path
        if path_only == "/" or path_only == "/index.html":
            self._send_html(_index_html())
            return
        if path_only == "/api/state":
            self._send_json(_current_state())
            return
        if path_only.startswith("/outputs/"):
            self._send_output_file(path_only)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        path_only = urlparse(self.path).path
        if path_only == "/run":
            try:
                payload = self._read_form()
                _update_inputs(payload)
                DuCOStateMachine().run()
                self.send_response(303)
                self.send_header("Location", "/?updated=1")
                self.end_headers()
            except Exception as exc:
                self._send_html(_index_html(error=str(exc)))
            return

        if path_only != "/api/run":
            self.send_error(404, "Not found")
            return

        try:
            payload = self._read_json()
            if payload:
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
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        parsed = parse_qs(raw)
        return {key: values[0] for key, values in parsed.items()}

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
            "pt_invoice": (DATA_DIR / "priya_pt_invoice.txt").read_text(encoding="utf-8"),
            "surgeon_estimate": (DATA_DIR / "surgeon_estimate.txt").read_text(encoding="utf-8"),
            "user_query": (DATA_DIR / "user_query.txt").read_text(encoding="utf-8"),
            "amounts": _input_amounts(),
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
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _input_amounts() -> dict[str, int]:
    pt_text = (DATA_DIR / "priya_pt_invoice.txt").read_text(encoding="utf-8")
    estimate_text = (DATA_DIR / "surgeon_estimate.txt").read_text(encoding="utf-8")
    return {
        "pt_amount": _extract_labeled_amount(pt_text, "Total charges", 30000),
        "acl_amount": _extract_cpt_amount(estimate_text, "29888", 350000),
        "meniscus_amount": _extract_cpt_amount(estimate_text, "29881", 100000),
        "surgery_total": _extract_labeled_amount(estimate_text, "Estimated total", 450000),
    }


def _extract_labeled_amount(text: str, label: str, default: int) -> int:
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*(?:INR|Rs\.?)?\s*([0-9,]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    return int(match.group(1).replace(",", ""))


def _extract_cpt_amount(text: str, cpt: str, default: int) -> int:
    pattern = rf"CPT\s*{re.escape(cpt)}\s*[-:]\s*.*?\s*[-:]\s*(?:INR|Rs\.?)?\s*([0-9,]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    return int(match.group(1).replace(",", ""))


def _update_inputs(payload: dict[str, object]) -> None:
    pt_amount = _amount_from_payload(payload, "pt_amount")
    surgery_total = _amount_from_payload(payload, "surgery_total")
    acl_amount = _amount_from_payload(payload, "acl_amount")
    meniscus_amount = _amount_from_payload(payload, "meniscus_amount")

    if pt_amount is not None:
        _replace_labeled_amount(DATA_DIR / "priya_pt_invoice.txt", "Total charges", pt_amount)
    if acl_amount is not None:
        _replace_cpt_amount(DATA_DIR / "surgeon_estimate.txt", "29888", acl_amount)
    if meniscus_amount is not None:
        _replace_cpt_amount(DATA_DIR / "surgeon_estimate.txt", "29881", meniscus_amount)
    if surgery_total is not None:
        _replace_labeled_amount(DATA_DIR / "surgeon_estimate.txt", "Estimated total", surgery_total)


def _amount_from_payload(payload: dict[str, object], key: str) -> int | None:
    value = str(payload.get(key, "")).strip().replace(",", "")
    if not value:
        return None
    return int(value)


def _replace_labeled_amount(path: Path, label: str, amount: int) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = f"{label}: INR {amount:,}"
    pattern = rf"{re.escape(label)}\s*[:\-].*"
    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    path.write_text(text, encoding="utf-8")


def _replace_cpt_amount(path: Path, cpt: str, amount: int) -> None:
    text = path.read_text(encoding="utf-8")
    pattern = rf"(CPT\s*{re.escape(cpt)}\s*[-:]\s*.*?\s*[-:]\s*)(?:INR|Rs\.?)?\s*[0-9,]+"
    text = re.sub(pattern, rf"\1INR {amount:,}", text, flags=re.IGNORECASE)
    path.write_text(text, encoding="utf-8")


def _index_html(error: str | None = None) -> str:
    state = _current_state()
    report = state["report"]
    if report is None:
        DuCOStateMachine().run()
        state = _current_state()
        report = state["report"]
    amounts = state["inputs"]["amounts"]
    summary = state["summary"]
    status = f"Error: {error}" if error else "Ready. Change values and click Run Analysis."
    status_class = "error" if error else ""
    cob = report["cob"] if report else {"claims": [], "total_charges_inr": 0, "total_insurer_paid_inr": 0, "household_out_of_pocket_inr": 0}
    claims_html = "\n".join(_claim_card(claim) for claim in cob["claims"])
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DuCO-Agent</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --ink: #18202f;
      --muted: #657083;
      --line: #dce2ec;
      --blue: #2563eb;
      --green: #059669;
      --red: #dc2626;
      --shadow: 0 14px 38px rgba(26, 35, 58, .09);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, Segoe UI, Arial, sans-serif;
    }
    header {
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }
    h1 { margin: 0; font-size: 24px; letter-spacing: 0; }
    .sub { color: var(--muted); margin-top: 4px; font-size: 14px; }
    button {
      border: 0;
      background: var(--blue);
      color: #fff;
      padding: 11px 16px;
      border-radius: 7px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }
    button:disabled { opacity: .62; cursor: wait; }
    .status {
      margin-top: 12px;
      padding: 10px 12px;
      border-radius: 7px;
      border: 1px solid var(--line);
      color: var(--muted);
      background: #fbfcff;
      font-size: 13px;
      font-weight: 700;
    }
    .status.ok { color: #047857; background: #ecfdf5; border-color: #a7f3d0; }
    .status.error { color: #b91c1c; background: #fef2f2; border-color: #fecaca; }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 390px) 1fr;
      gap: 18px;
      padding: 18px;
      max-width: 1380px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .panel-title {
      padding: 15px 16px;
      border-bottom: 1px solid var(--line);
      font-weight: 800;
    }
    .panel-body { padding: 16px; }
    label { display: block; font-size: 12px; color: var(--muted); font-weight: 800; margin-bottom: 7px; }
    input {
      width: 100%;
      height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
      margin-bottom: 13px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcff;
    }
    .metric span { display: block; color: var(--muted); font-size: 12px; font-weight: 800; }
    .metric strong { display: block; margin-top: 8px; font-size: 22px; }
    .claims {
      display: grid;
      grid-template-columns: repeat(2, minmax(260px, 1fr));
      gap: 12px;
    }
    .claim {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .claim h3 { margin: 0 0 12px; font-size: 16px; }
    .row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid #edf1f6;
      padding: 9px 0;
      font-size: 14px;
    }
    .row:first-of-type { border-top: 0; }
    .tag {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eef6ff;
      color: #1d4ed8;
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 10px;
    }
    .chart {
      width: 100%;
      min-height: 190px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      margin-top: 16px;
    }
    .letters {
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 16px;
    }
    .letters a {
      color: var(--blue);
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 10px;
      text-decoration: none;
      font-weight: 700;
      background: #fff;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      font-family: Consolas, ui-monospace, monospace;
      font-size: 13px;
      line-height: 1.45;
      color: #253044;
    }
    .summary {
      max-height: 270px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcff;
      margin-top: 16px;
    }
    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      main { grid-template-columns: 1fr; }
      .metrics, .claims, .letters { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>DuCO-Agent Dashboard</h1>
      <div class="sub">Run Coordination of Benefits analysis and review patient-ready outputs.</div>
    </div>
  </header>
  <main>
    <section>
      <div class="panel-title">Input Amounts</div>
      <div class="panel-body">
        <form method="post" action="/run">
        <label for="ptAmount">Priya PT bill</label>
        <input id="ptAmount" name="pt_amount" inputmode="numeric" value="__PT_AMOUNT__">
        <label for="aclAmount">Aarav ACL reconstruction CPT 29888</label>
        <input id="aclAmount" name="acl_amount" inputmode="numeric" value="__ACL_AMOUNT__">
        <label for="meniscusAmount">Aarav meniscectomy CPT 29881</label>
        <input id="meniscusAmount" name="meniscus_amount" inputmode="numeric" value="__MENISCUS_AMOUNT__">
        <label for="surgeryTotal">Aarav surgery estimated total</label>
        <input id="surgeryTotal" name="surgery_total" inputmode="numeric" value="__SURGERY_TOTAL__">
        <button id="runBtn" type="submit">Run Analysis</button>
        </form>
        <div class="sub">Changes are written to the data text files, then the agent runs fresh.</div>
        <div class="status __STATUS_CLASS__" id="status">__STATUS__</div>
      </div>
    </section>
    <section>
      <div class="panel-title">Results</div>
      <div class="panel-body">
        <div class="metrics">
          <div class="metric"><span>Total Charges</span><strong id="totalCharges">__TOTAL_CHARGES__</strong></div>
          <div class="metric"><span>Insurer Paid</span><strong id="insurerPaid">__INSURER_PAID__</strong></div>
          <div class="metric"><span>Patient Pays</span><strong id="patientPays">__PATIENT_PAYS__</strong></div>
        </div>
        <div class="claims" id="claims">__CLAIMS__</div>
        <img class="chart" id="chart" src="/outputs/charts/cost_flow.svg" alt="COB cost flow chart">
        <div class="letters">
          <a href="/outputs/preauth_letters/aarav_plan_b_primary_preauth.txt" target="_blank">Aarav Plan B Letter</a>
          <a href="/outputs/preauth_letters/aarav_plan_a_secondary_preauth.txt" target="_blank">Aarav Plan A Letter</a>
          <a href="/outputs/preauth_letters/priya_pt_claim_cover_letter.txt" target="_blank">Priya PT Letter</a>
        </div>
        <div class="summary"><pre id="summary">__SUMMARY__</pre></div>
      </div>
    </section>
  </main>
  <script>
    const fmt = value => `INR ${Number(value || 0).toLocaleString('en-IN')}`;
    const clean = value => String(value || '').replaceAll(',', '').trim();

    async function loadState() {
      const res = await fetch('/api/state');
      const data = await res.json();
      if (data.inputs && data.inputs.amounts) setInputs(data.inputs.amounts);
      if (data.report) render(data.summary, data.report);
    }

    async function runAnalysis() {
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Running...';
      const payload = {
        pt_amount: clean(document.getElementById('ptAmount').value),
        acl_amount: clean(document.getElementById('aclAmount').value),
        meniscus_amount: clean(document.getElementById('meniscusAmount').value),
        surgery_total: clean(document.getElementById('surgeryTotal').value)
      };
      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'Analysis failed');
        if (data.inputs) setInputs(data.inputs);
        render(data.summary, data.report);
        setStatus('Updated from latest input values.', 'ok');
      } catch (err) {
        setStatus(err.message || String(err), 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Run Analysis';
      }
    }

    function setInputs(amounts) {
      document.getElementById('ptAmount').value = amounts.pt_amount;
      document.getElementById('aclAmount').value = amounts.acl_amount;
      document.getElementById('meniscusAmount').value = amounts.meniscus_amount;
      document.getElementById('surgeryTotal').value = amounts.surgery_total;
    }

    function setStatus(message, kind = '') {
      const status = document.getElementById('status');
      status.textContent = message;
      status.className = `status ${kind}`.trim();
    }

    function render(summary, report) {
      const cob = report.cob;
      document.getElementById('totalCharges').textContent = fmt(cob.total_charges_inr);
      document.getElementById('insurerPaid').textContent = fmt(cob.total_insurer_paid_inr);
      document.getElementById('patientPays').textContent = fmt(cob.household_out_of_pocket_inr);
      document.getElementById('summary').textContent = summary || '';
      document.getElementById('chart').src = `/outputs/charts/cost_flow.svg?t=${Date.now()}`;
      document.getElementById('claims').innerHTML = cob.claims.map(claim => `
        <article class="claim">
          <span class="tag">${claim.preauth_required ? 'Pre-auth required' : 'No pre-auth'}</span>
          <h3>${claim.member_name}</h3>
          <div class="row"><span>Service</span><strong>${claim.description}</strong></div>
          <div class="row"><span>Charge</span><strong>${fmt(claim.charge_inr)}</strong></div>
          <div class="row"><span>Primary</span><strong>${claim.primary_plan_label}</strong></div>
          <div class="row"><span>Primary paid</span><strong>${fmt(claim.primary_paid_inr)}</strong></div>
          <div class="row"><span>Secondary paid</span><strong>${fmt(claim.secondary_paid_inr)}</strong></div>
          <div class="row"><span>Patient</span><strong>${fmt(claim.patient_paid_inr)}</strong></div>
        </article>
      `).join('');
    }

    const form = document.querySelector('form');
    form.addEventListener('submit', () => {{
      const btn = document.getElementById('runBtn');
      btn.disabled = true;
      btn.textContent = 'Running...';
      setStatus('Running analysis...', '');
    }});
  </script>
</body>
</html>"""
    return (
        html.replace("__PT_AMOUNT__", str(amounts["pt_amount"]))
        .replace("__ACL_AMOUNT__", str(amounts["acl_amount"]))
        .replace("__MENISCUS_AMOUNT__", str(amounts["meniscus_amount"]))
        .replace("__SURGERY_TOTAL__", str(amounts["surgery_total"]))
        .replace("__STATUS_CLASS__", status_class)
        .replace("__STATUS__", _html_escape(status))
        .replace("__TOTAL_CHARGES__", _format_inr_for_ui(cob["total_charges_inr"]))
        .replace("__INSURER_PAID__", _format_inr_for_ui(cob["total_insurer_paid_inr"]))
        .replace("__PATIENT_PAYS__", _format_inr_for_ui(cob["household_out_of_pocket_inr"]))
        .replace("__CLAIMS__", claims_html)
        .replace("__SUMMARY__", _html_escape(summary))
    )


def _claim_card(claim: dict[str, object]) -> str:
    tag = "Pre-auth required" if claim["preauth_required"] else "No pre-auth"
    return f"""
        <article class="claim">
          <span class="tag">{tag}</span>
          <h3>{_html_escape(str(claim["member_name"]))}</h3>
          <div class="row"><span>Service</span><strong>{_html_escape(str(claim["description"]))}</strong></div>
          <div class="row"><span>Charge</span><strong>{_format_inr_for_ui(int(claim["charge_inr"]))}</strong></div>
          <div class="row"><span>Primary</span><strong>{_html_escape(str(claim["primary_plan_label"]))}</strong></div>
          <div class="row"><span>Primary paid</span><strong>{_format_inr_for_ui(int(claim["primary_paid_inr"]))}</strong></div>
          <div class="row"><span>Secondary paid</span><strong>{_format_inr_for_ui(int(claim["secondary_paid_inr"]))}</strong></div>
          <div class="row"><span>Patient</span><strong>{_format_inr_for_ui(int(claim["patient_paid_inr"]))}</strong></div>
        </article>
"""


def _format_inr_for_ui(amount: int) -> str:
    return f"INR {amount:,}"


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DuCORequestHandler)
    print("DuCO-Agent UI running at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
