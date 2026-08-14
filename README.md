# DuCO-Agent AI Assessment

DuCO-Agent is a demo project for Priya and Aarav Sen's dual health insurance scenario. It reads mock medical documents, identifies the important claim details, applies Coordination of Benefits rules, and generates useful outputs such as claim summaries, pre-authorization letters, and a cost-flow chart.

## Architecture

```text
Intake Agent -> Clinical Agent -> COB Agent -> Output Agent
```

- Intake Agent reads the invoice, MRI report, surgeon estimate, and user query.
- Clinical Agent adds diagnosis, ICD-10, CPT codes, and pre-authorization decisions.
- COB Agent decides primary/secondary payer order and calculates payments.
- Output Agent writes the summary, final JSON, letters, chart, briefing text, and optional WAV audio briefing. The dashboard also includes browser text-to-speech playback for the briefing.

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

Uploaded documents replace the matching files under `data/`, refresh the extracted `.txt` files, rerun the agents, and update the dashboard. PDF parsing uses PyMuPDF. Image OCR uses Pillow, pytesseract, and the Tesseract OCR engine. If Gemini credentials are configured, Gemini Vision can be used as an OCR/metadata fallback when local OCR cannot read an uploaded image.

The checked-in `.txt` files beside the sample images/PDF are OCR/PDF sidecar cache files. They keep the default demo stable when OCR is not installed locally. When a user uploads a new PNG, JPG, or PDF through the dashboard, the app parses that uploaded file and refreshes the matching sidecar text before running the agents.

The dashboard also shows agent traces from `router_decisions` and `run_log`, so reviewers can see which agents ran and why. The "Play Audio Briefing" button uses the browser's built-in text-to-speech support.

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

The UI writes manual amount changes to:

- `data/priya_pt_invoice.txt`
- `data/surgeon_estimate.txt`

Uploaded documents also refresh the matching sidecar `.txt` files from the uploaded image/PDF content. Then the app reruns the full workflow and refreshes the dashboard. Do not run `scripts/create_mock_data.py` after manual edits unless you want to reset the default data.

## Outputs

- `outputs/summary.txt`
- `outputs/final_report.json`
- `outputs/audit_log.jsonl`
- `outputs/preauth_letters/`
- `outputs/charts/cost_flow.svg`
- `outputs/charts/cost_flow.png`
- `outputs/audio_briefing.txt`
- `outputs/audio_briefing.wav` when local TTS is available

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

## Mock Rule APIs

CPT and pre-authorization rules are stored as JSON-backed mock APIs:

- `data/mock_rules/cpt_rules.json`
- `data/mock_rules/preauth_rules.json`
- `utils/mock_apis.py`

The Clinical Agent queries these mock APIs before falling back to local deterministic defaults.

## Security Notes

- The dashboard binds to `127.0.0.1` for local demo use.
- Secrets are read from environment variables only.
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` is optional; deterministic fallbacks are used when absent.
- `DUCO_UI_TOKEN` can be used for local token protection.

## Optional Gemini Key

For Gemini-assisted clinical interpretation, optional Gemini Vision OCR fallback, and optional LLM judge validation, copy `.env.example` to `.env` and replace the placeholder value:

```text
GEMINI_API_KEY=your-real-api-key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_VISION_MODEL=gemini-2.5-flash
```

Do not commit `.env`; it is intentionally ignored by Git.

## Deploy On Cloud Run

The app is Cloud Run ready through `Dockerfile`. It listens on the `PORT` environment variable and installs Tesseract OCR inside the container.

Basic deployment:

```powershell
gcloud run deploy duco-agent-ai-assessment --source . --region asia-south1
```

Set runtime variables in Cloud Run:

```text
GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
DUCO_UI_TOKEN
```
