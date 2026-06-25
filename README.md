# DuCO-Agent AI Assessment

DuCO-Agent is a practical agentic Coordination of Benefits (COB) system for Priya and Aarav Sen's dual-coverage insurance scenario. It ingests mock multi-modal medical inputs, extracts clinical and billing facts, applies COB rules, and generates patient-friendly financial and pre-authorization outputs.

## Architecture

```text
DuCO-Agent
|
+-- Intake Agent     -> parses image, PDF, estimate, and user transcript inputs
+-- Clinical Agent   -> infers diagnoses, CPT/ICD codes, and pre-auth needs
+-- COB Agent        -> determines primary/secondary plans and calculates INR payments
+-- Output Agent     -> writes summaries, letters, machine JSON, and cost-flow visuals
```

The workflow is intentionally between a single script and a full enterprise graph. `main.py` runs a small state machine with validation checkpoints and bounded repair loops after each agent.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/create_mock_data.py
python main.py
```

To use the browser UI instead:

```bash
python web_app.py
```

Then open `http://127.0.0.1:8000`.

If optional OCR/PDF/chart dependencies are unavailable, the app still runs with deterministic sidecar fallbacks. This makes the demo reliable while keeping the code ready for real OCR and PDF extraction.

## Changing Input Amounts

For quick demos, edit these text sidecars in VS Code:

- `data/priya_pt_invoice.txt`
- `data/surgeon_estimate.txt`

Then run:

```bash
python main.py
```

Do not run `python scripts/create_mock_data.py` after manual edits unless you want to reset the mock files back to the default assessment values.

## Outputs

After `python main.py`, inspect:

- `outputs/summary.txt`
- `outputs/final_report.json`
- `outputs/preauth_letters/aarav_plan_a_secondary_preauth.txt`
- `outputs/preauth_letters/aarav_plan_b_primary_preauth.txt`
- `outputs/preauth_letters/priya_pt_claim_cover_letter.txt`
- `outputs/charts/cost_flow.svg`
- `outputs/charts/cost_flow.png`
- `outputs/audio_briefing.txt`

## Mock Insurance Assumptions

For spouses, each person's own employer policy is primary and the spouse's policy is secondary:

- Aarav surgery: primary `Plan B / Insurer2`; secondary `Plan A / Insurer1`
- Priya PT: primary `Plan A / Insurer1`; secondary `Plan B / Insurer2`

The plan terms are stored in `utils/insurance_rules.py`, not hidden inside the COB agent. The secondary plan pays remaining patient liability up to its configured secondary residual coverage, after cross-plan deductible credit is applied.

## Assessment Notes

- Agentic behavior: state transitions, validation, reflection notes, and bounded repair loops.
- Multi-modal ingestion: image OCR, PDF text extraction, and text transcript parsing with fallbacks.
- Accuracy: explicit COB assumptions, deductible/coinsurance calculations, and INR rounding.
- Usability: patient summary, insurer letters, JSON output, and cost flow chart.

## Git Workflow Reminder

Create the GitHub repo as private and work from a feature branch, for example:

```bash
git switch -c feature/duco-agent
git add .
git commit -m "feat: build duco agent cob workflow"
```

Then open a pull request into `main`.
