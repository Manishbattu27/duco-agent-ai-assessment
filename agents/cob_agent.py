from __future__ import annotations

from typing import Any

from utils.insurance_rules import COBRulesEngine, format_inr
from utils.validation import ValidationResult


class COBAgent:
    def __init__(self) -> None:
        self.rules = COBRulesEngine()

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        clinical = state["clinical"]
        adjudicated = []
        for claim in clinical["claims"]:
            adjudicated.append(self.rules.adjudicate_claim(claim))

        cob_data = {
            "claims": adjudicated,
            "household_out_of_pocket_inr": sum(item["patient_paid_inr"] for item in adjudicated),
            "total_charges_inr": sum(item["charge_inr"] for item in adjudicated),
            "total_insurer_paid_inr": sum(
                item["primary_paid_inr"] + item["secondary_paid_inr"] for item in adjudicated
            ),
        }
        cob_data["patient_message"] = self._patient_message(cob_data)
        return {"cob": cob_data, "validation": self._validate(cob_data)}

    def _patient_message(self, cob_data: dict[str, Any]) -> str:
        lines = [
            "Coordination of Benefits result:",
            f"Total charges: {format_inr(cob_data['total_charges_inr'])}",
            f"Total insurer payments: {format_inr(cob_data['total_insurer_paid_inr'])}",
            f"Estimated household out-of-pocket: {format_inr(cob_data['household_out_of_pocket_inr'])}",
        ]
        return "\n".join(lines)

    def _validate(self, cob_data: dict[str, Any]) -> ValidationResult:
        issues = []
        for claim in cob_data["claims"]:
            paid_total = claim["primary_paid_inr"] + claim["secondary_paid_inr"] + claim["patient_paid_inr"]
            if paid_total != claim["charge_inr"]:
                issues.append(
                    f"{claim['claim_id']} payment mismatch: charge={claim['charge_inr']} paid={paid_total}"
                )
            if claim["primary_plan"] == claim["secondary_plan"]:
                issues.append(f"{claim['claim_id']} has same primary and secondary plan.")
        return ValidationResult(ok=not issues, issues=issues)
