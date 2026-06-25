from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def format_inr(amount: int) -> str:
    return "INR " + f"{amount:,}"


@dataclass(frozen=True)
class Plan:
    id: str
    label: str
    insurer: str
    deductible_remaining_inr: int
    coinsurance_rate: float
    secondary_residual_coverage_rate: float


class COBRulesEngine:
    """Mock COB engine with explicit, explainable plan terms."""

    plans = {
        "plan_a": Plan(
            id="plan_a",
            label="Plan A",
            insurer="Insurer1",
            deductible_remaining_inr=10000,
            coinsurance_rate=0.10,
            secondary_residual_coverage_rate=1.00,
        ),
        "plan_b": Plan(
            id="plan_b",
            label="Plan B",
            insurer="Insurer2",
            deductible_remaining_inr=30000,
            coinsurance_rate=0.20,
            secondary_residual_coverage_rate=1.00,
        ),
    }

    primary_by_person = {
        "priya": "plan_a",
        "aarav": "plan_b",
    }

    member_names = {
        "priya": "Priya Sen",
        "aarav": "Aarav Sen",
    }

    def adjudicate_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        primary_id = self.primary_by_person[claim["person"]]
        secondary_id = "plan_b" if primary_id == "plan_a" else "plan_a"
        primary = self.plans[primary_id]
        secondary = self.plans[secondary_id]

        charge = int(claim["charge_inr"])
        primary_result = self._primary_payment(charge, primary)
        residual = charge - primary_result["paid_inr"]

        secondary_paid = self._secondary_payment(
            residual_inr=residual,
            primary_deductible_applied_inr=primary_result["deductible_applied_inr"],
            secondary=secondary,
        )
        patient_paid = charge - primary_result["paid_inr"] - secondary_paid

        return {
            **claim,
            "member_name": self.member_names[claim["person"]],
            "primary_plan": primary.id,
            "primary_plan_label": f"{primary.insurer} / {primary.label}",
            "secondary_plan": secondary.id,
            "secondary_plan_label": f"{secondary.insurer} / {secondary.label}",
            "allowed_amount_inr": charge,
            "primary_deductible_applied_inr": primary_result["deductible_applied_inr"],
            "primary_coinsurance_inr": primary_result["coinsurance_inr"],
            "primary_paid_inr": primary_result["paid_inr"],
            "secondary_paid_inr": secondary_paid,
            "patient_paid_inr": patient_paid,
            "cob_explanation": self._explanation(
                charge, primary, secondary, primary_result, secondary_paid, patient_paid
            ),
        }

    def _primary_payment(self, charge: int, plan: Plan) -> dict[str, int]:
        deductible = min(charge, plan.deductible_remaining_inr)
        after_deductible = charge - deductible
        coinsurance = round(after_deductible * plan.coinsurance_rate)
        paid = charge - deductible - coinsurance
        return {
            "deductible_applied_inr": deductible,
            "coinsurance_inr": coinsurance,
            "paid_inr": paid,
        }

    def _secondary_payment(
        self,
        residual_inr: int,
        primary_deductible_applied_inr: int,
        secondary: Plan,
    ) -> int:
        deductible_credit = secondary.deductible_remaining_inr if primary_deductible_applied_inr else 0
        secondary_remaining_deductible = max(secondary.deductible_remaining_inr - deductible_credit, 0)
        covered_residual = max(residual_inr - secondary_remaining_deductible, 0)
        return min(residual_inr, round(covered_residual * secondary.secondary_residual_coverage_rate))

    def _explanation(
        self,
        charge: int,
        primary: Plan,
        secondary: Plan,
        primary_result: dict[str, int],
        secondary_paid: int,
        patient_paid: int,
    ) -> str:
        return (
            f"{primary.insurer}/{primary.label} is primary and pays {format_inr(primary_result['paid_inr'])} "
            f"after {format_inr(primary_result['deductible_applied_inr'])} deductible and "
            f"{format_inr(primary_result['coinsurance_inr'])} coinsurance. "
            f"{secondary.insurer}/{secondary.label} is secondary and pays {format_inr(secondary_paid)} "
            f"toward the residual. Patient responsibility is {format_inr(patient_paid)} "
            f"on {format_inr(charge)} allowed charges."
        )
