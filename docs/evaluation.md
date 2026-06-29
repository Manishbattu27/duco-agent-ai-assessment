# Evaluation Scenarios

## Benchmark Scenario

Default assessment inputs:

- Priya PT bill: INR 30,000.
- Aarav ACL reconstruction and meniscectomy: INR 450,000.

Expected result:

- Total charges: INR 480,000.
- Total insurer payments: INR 480,000.
- Household out-of-pocket: INR 0.
- Aarav Plan B primary payment: INR 336,000.
- Aarav Plan A secondary payment: INR 114,000.
- Priya Plan A primary payment: INR 18,000.
- Priya Plan B secondary payment: INR 12,000.

## Dynamic Input Scenario

Change UI values:

- Priya PT: INR 40,000.
- Aarav surgery estimated total: INR 550,000.

Expected behavior:

- Dashboard reloads with recalculated totals.
- `outputs/final_report.json` reflects the new charge amounts.
- `outputs/audit_log.jsonl` captures the new run.

## Failure Scenarios

- Missing MRI ACL evidence should fail Intake validation.
- Surgery without CPT preauthorization codes should fail Clinical validation.
- COB payment totals not balancing to charge should fail COB validation.
- Missing generated files should fail Output validation.

## Automated Coverage

The test suite covers:

- Default Aarav and Priya COB payment balancing.
- Allowed amount, non-covered amount, copay, OOP cap, and deductible behavior.
- Secondary lesser-of coordination behavior.
- Contract validation failure detection.
- UI amount input validation.
- Image sidecar refresh using OCR output rather than stale sidecar text.
- PDF sidecar refresh from a generated text PDF.
- Upload refresh behavior for PNG, JPG, and PDF files.
