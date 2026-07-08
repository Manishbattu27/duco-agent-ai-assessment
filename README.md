# DuCO-Agent AI Assessment

DuCO-Agent is a demo project for Priya and Aarav Sen's dual health insurance scenario. It reads mock medical documents, identifies the important claim details, applies Coordination of Benefits rules, and generates useful outputs such as claim summaries, pre-authorization letters, and a cost-flow chart.

## Architecture

```text
Intake Agent -> Clinical Agent -> COB Agent -> Output Agent
```

- Intake Agent reads the invoice, MRI report, surgeon estimate, and user query.
- Clinical Agent adds diagnosis, ICD-10, CPT codes, and pre-authorization decisions.
- COB Agent decides primary/secondary payer order and calculates payments.
- Output Agent writes the summary, final JSON, letters, chart, and briefing text.

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

The dashboard supports two ways to run the analysis:

- Document uploads for `priya_pt_invoice.png`, `aarav_mri_report.pdf`, and `surgeon_estimate.jpg`.
- Manual amount fields for quick recalculation when documents are not readable or when testing different cost scenarios.

Uploaded documents replace the matching files under `data/`, refresh the extracted `.txt` files, rerun the agents, and update the dashboard. PDF parsing uses PyMuPDF. Image OCR uses Pillow, pytesseract, and the Tesseract OCR engine.

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

Then it reruns the full workflow and refreshes the dashboard. Do not run `scripts/create_mock_data.py` after manual edits unless you want to reset the default data.

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
- Total insurer payments: INR 468,000.
- Household out-of-pocket: INR 12,000.

## COB Rule Coverage

The rules engine models:

- Primary and secondary payer order.
- Billed and allowed amounts.
- Non-covered balance.
- Deductible remaining.
- Copay by claim type.
- Coinsurance.
- Out-of-pocket remaining cap.
- Lesser-of secondary coordination: the secondary payer does not pay more than the remaining liability or more than its own policy would allow.

## Security Notes

- The dashboard binds to `127.0.0.1` for local demo use.
- Secrets are read from environment variables only.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` is optional; deterministic fallbacks are used when absent.
- `DUCO_UI_TOKEN` can be used for local token protection.

## Optional Gemini Key

For Gemini-assisted clinical interpretation, copy `.env.example` to `.env` and replace the placeholder value:

```text
GEMINI_API_KEY=your-real-api-key
GEMINI_MODEL=gemini-2.5-flash
```

Do not commit `.env`; it is intentionally ignored by Git.
