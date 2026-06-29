# Operations

## Local Runtime

Command line:

```bash
python main.py
```

Dashboard:

```bash
python web_app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Document Upload Parsing

The dashboard accepts:

- Priya PT invoice: `.png`
- Aarav MRI report: `.pdf`
- Surgeon estimate: `.jpg` or `.jpeg`

On upload, the app:

1. Saves the document into `data/`.
2. Extracts text into the matching `.txt` sidecar.
3. Runs `DuCOStateMachine`.
4. Refreshes dashboard results.

PDF parsing requires `PyMuPDF`. Image parsing requires `Pillow`, `pytesseract`, and the Tesseract OCR engine installed locally.

Run extraction and COB tests with:

```bash
python -m pytest -q
```

## Optional Local UI Token

Set `DUCO_UI_TOKEN` before starting the UI to require a token for API/form requests.

```powershell
$env:DUCO_UI_TOKEN="replace-with-local-token"
python web_app.py
```

Then open:

```text
http://127.0.0.1:8000/?token=replace-with-local-token
```

## Monitoring

The demo writes:

- `outputs/final_report.json`
- `outputs/audit_log.jsonl`

These provide run metadata, validation results, and step-level execution traces.

## Rollback

Because all generated artifacts are local files, rollback is:

1. Revert input files under `data/`.
2. Rerun `python main.py`.
3. Or restore from Git using a previous commit.

## Support

For failures, inspect:

- UI error banner.
- Terminal traceback.
- `outputs/audit_log.jsonl`.
- `outputs/final_report.json`.
