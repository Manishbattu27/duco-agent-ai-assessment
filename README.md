# DuCO-Agent AI Assessment

DuCO-Agent is an agentic Coordination of Benefits system for Priya and Aarav Sen's dual-coverage health insurance scenario. It ingests mock multi-modal medical inputs, infers clinical codes, applies COB rules, calculates out-of-pocket cost, and generates patient-facing and insurer-facing outputs.

## Architecture

```text
Intake Agent -> Clinical Agent -> COB Agent -> Output Agent
```

- Intake Agent parses invoices, MRI reports, estimates, and user transcript files.
- Clinical Agent adds diagnoses, ICD-10, CPT codes, and preauthorization decisions.
- COB Agent applies primary/secondary payer rules and payment math.
- Output Agent writes summaries, JSON reports, preauthorization letters, charts, and audio briefing text.

Detailed docs:

- `docs/architecture.md`
- `docs/tool_contracts.md`
- `docs/assessment_readiness.md`
- `docs/evaluation.md`
- `docs/operations.md`
- `docs/security.md`

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/create_mock_data.py
python main.py
```

## Dashboard

```bash
python web_app.py
```

Open:

```text
http://127.0.0.1:8000
```

The dashboard has two input paths:

- Document uploads for `priya_pt_invoice.png`, `aarav_mri_report.pdf`, and `surgeon_estimate.jpg`.
- Manual amount fields for quick recalculation when documents are not readable or when testing different insurance cost scenarios.

Uploaded documents replace the matching files under `data/`, refresh the extracted `.txt` sidecars, rerun the agents, and update the dashboard. PDF text extraction uses PyMuPDF. Image OCR uses Pillow + pytesseract and requires the Tesseract OCR engine to be installed on the machine.

Optional local UI token:

```powershell
$env:DUCO_UI_TOKEN="replace-with-local-token"
python web_app.py
```

Open:

```text
http://127.0.0.1:8000/?token=replace-with-local-token
```

## Dynamic Inputs

The UI writes to:

- `data/priya_pt_invoice.txt`
- `data/surgeon_estimate.txt`

Then it reruns the full state machine and refreshes the dashboard. Do not run `scripts/create_mock_data.py` after manual edits unless you want to reset default data.

## Outputs

- `outputs/summary.txt`
- `outputs/final_report.json`
- `outputs/audit_log.jsonl`
- `outputs/preauth_letters/`
- `outputs/charts/cost_flow.svg`
- `outputs/charts/cost_flow.png`
- `outputs/audio_briefing.txt`

## Default Expected Result

- Total charges: INR 480,000.
- Total insurer payments: INR 480,000.
- Household out-of-pocket: INR 0.

## COB Rule Coverage

The rules engine models:

- Primary and secondary payer order.
- Billed and allowed amounts.
- Non-covered balance.
- Deductible remaining.
- Copay by claim type.
- Coinsurance.
- Out-of-pocket remaining cap.
- Residual and lesser-of secondary coordination methods.

## Security Notes

- The dashboard binds to `127.0.0.1` for local demo use.
- Secrets are read from environment variables only.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` is optional; deterministic fallbacks are used when absent.
- `DUCO_UI_TOKEN` can be used for local token protection.
