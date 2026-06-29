# Assessment Readiness

## Scope

In scope:

- Priya and Aarav Sen dual-coverage scenario.
- Mock image/PDF/text ingestion with deterministic sidecar fallbacks.
- CPT/ICD inference for PT and ACL/meniscus surgery.
- Primary/secondary payer selection.
- Allowed amount, deductible, copay, coinsurance, OOP cap, residual secondary coverage, lesser-of secondary coordination, and patient liability calculation.
- Preauthorization and claim letter generation.
- Local dashboard and command-line execution.

Out of scope:

- Real insurer API submission.
- Real patient authentication portal.
- Production claims clearinghouse integration.
- Legal guarantee of medical coding correctness.
- Persistent user account storage.

## Checklist Coverage

- Problem and business objective: README and scenario-specific docs.
- Architecture: `docs/architecture.md`.
- Agent responsibilities and boundaries: documented and enforced by separate modules.
- Business logic separated from prompts: COB rules live in `utils/insurance_rules.py`.
- Structured contracts: `utils/contracts.py` and `docs/tool_contracts.md`.
- Deterministic outputs: fallback extraction, deterministic clinical inference, and structured final JSON.
- Controlled failures: validation results, UI error responses, and audit events.
- Secrets: optional Gemini and UI token read from environment variables only.
- Workflow state: per-run `DuCOStateMachine.state`, separate from any conversation history.
- Audit trail: `outputs/audit_log.jsonl` and `run_log` in `outputs/final_report.json`.
- Tests: `tests/test_cob_rules.py`, `tests/test_contracts_and_inputs.py`, and `tests/test_extraction_pipeline.py`.
- Security and local access controls: `docs/security.md`.

## Known Limitations

- The local UI binds to `127.0.0.1` and is intended for demo/runtime use, not internet exposure.
- Formal production auth can be added behind the existing `DUCO_UI_TOKEN` hook.
- Medical coding is mock-validated and should be reviewed by a certified coder before real claims use.
