from __future__ import annotations

from typing import Any

from utils.validation import ValidationResult


TOOL_CONTRACTS: dict[str, dict[str, Any]] = {
    "intake_agent": {
        "input": {"state": "workflow state dictionary"},
        "output": {
            "intake.raw_documents": "source text extracted from invoice, MRI, estimate, and user query",
            "intake.people": "member and plan enrollment map",
            "intake.claims": "structured claim list with charge_inr and source metadata",
        },
        "required_output_fields": ["raw_documents", "people", "claims"],
    },
    "clinical_agent": {
        "input": {"intake.claims": "structured claims from Intake Agent"},
        "output": {
            "clinical.claims": "claims enriched with diagnosis, ICD-10, CPT, preauth, and rationale",
            "clinical.medical_summary": "short clinical summary for downstream letters",
        },
        "required_output_fields": ["claims", "medical_summary"],
    },
    "cob_agent": {
        "input": {"clinical.claims": "clinically enriched claims"},
        "output": {
            "cob.claims": "adjudicated claims with primary, secondary, and patient amounts",
            "cob.total_charges_inr": "household submitted charges",
            "cob.total_insurer_paid_inr": "combined insurer payments",
            "cob.household_out_of_pocket_inr": "estimated patient responsibility",
        },
        "required_output_fields": [
            "claims",
            "total_charges_inr",
            "total_insurer_paid_inr",
            "household_out_of_pocket_inr",
        ],
    },
    "output_agent": {
        "input": {"intake": "source data", "clinical": "clinical enrichment", "cob": "adjudication result"},
        "output": {
            "outputs.summary": "patient readable summary text path",
            "outputs.final_report": "machine readable JSON report path",
            "outputs.letters": "preauthorization and claim letter paths",
            "outputs.charts": "cost-flow visual paths",
            "outputs.audio_file": "optional generated WAV audio briefing path",
        },
        "required_output_fields": ["summary", "final_report", "audio_briefing", "letters", "charts"],
    },
}


def validate_contract(tool_name: str, payload: dict[str, Any]) -> ValidationResult:
    contract = TOOL_CONTRACTS[tool_name]
    issues = []
    for field in contract["required_output_fields"]:
        if field not in payload:
            issues.append(f"{tool_name} missing required output field: {field}")
    return ValidationResult(ok=not issues, issues=issues)
