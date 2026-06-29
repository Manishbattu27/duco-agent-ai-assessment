from __future__ import annotations

from dataclasses import dataclass, field
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
    out_of_pocket_remaining_inr: int = 1_000_000
    allowed_amount_rate: float = 1.0
    copay_by_claim_type: dict[str, int] = field(default_factory=dict)
    secondary_coordination_method: str = "residual"


class COBRulesEngine:
    """Mock COB engine with explicit, explainable plan terms."""

    default_plans = {
        "plan_a": Plan(
            id="plan_a",
            label="Plan A",
            insurer="Insurer1",
            deductible_remaining_inr=10000,
            coinsurance_rate=0.10,
            secondary_residual_coverage_rate=1.00,
            copay_by_claim_type={"physical_therapy": 0, "surgery": 0},
        ),
        "plan_b": Plan(
            id="plan_b",
            label="Plan B",
            insurer="Insurer2",
            deductible_remaining_inr=30000,
            coinsurance_rate=0.20,
            secondary_residual_coverage_rate=1.00,
            copay_by_claim_type={"physical_therapy": 0, "surgery": 0},
        ),
    }

    default_primary_by_person = {
        "priya": "plan_a",
        "aarav": "plan_b",
    }

    member_names = {
        "priya": "Priya Sen",
        "aarav": "Aarav Sen",
    }

    def __init__(
        self,
        plans: dict[str, Plan] | None = None,
        primary_by_person: dict[str, str] | None = None,
    ) -> None:
        self.plans = plans or self.default_plans
        self.primary_by_person = primary_by_person or self.default_primary_by_person

    def adjudicate_claim(self, claim: dict[str, Any]) -> dict[str, Any]:
        primary_id = self.primary_by_person[claim["person"]]
        secondary_id = "plan_b" if primary_id == "plan_a" else "plan_a"
        primary = self.plans[primary_id]
        secondary = self.plans[secondary_id]

        charge = int(claim["charge_inr"])
        primary_result = self._primary_payment(charge, primary, claim["claim_type"])
        residual = charge - primary_result["paid_inr"]

        secondary_paid = self._secondary_payment(
            charge_inr=charge,
            claim_type=claim["claim_type"],
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
            "billed_amount_inr": charge,
            "allowed_amount_inr": primary_result["allowed_amount_inr"],
            "non_covered_amount_inr": primary_result["non_covered_amount_inr"],
            "primary_copay_inr": primary_result["copay_inr"],
            "primary_deductible_applied_inr": primary_result["deductible_applied_inr"],
            "primary_coinsurance_inr": primary_result["coinsurance_inr"],
            "primary_oop_applied_inr": primary_result["oop_applied_inr"],
            "primary_paid_inr": primary_result["paid_inr"],
            "secondary_paid_inr": secondary_paid,
            "patient_paid_inr": patient_paid,
            "cob_explanation": self._explanation(
                charge, primary, secondary, primary_result, secondary_paid, patient_paid
            ),
        }

    def _primary_payment(self, charge: int, plan: Plan, claim_type: str) -> dict[str, int]:
        allowed = min(charge, round(charge * plan.allowed_amount_rate))
        non_covered = charge - allowed
        deductible = min(allowed, plan.deductible_remaining_inr)
        after_deductible = allowed - deductible
        copay = min(plan.copay_by_claim_type.get(claim_type, 0), after_deductible)
        after_copay = after_deductible - copay
        coinsurance = round(after_copay * plan.coinsurance_rate)
        member_cost_share = min(deductible + copay + coinsurance, plan.out_of_pocket_remaining_inr)
        paid = max(allowed - member_cost_share, 0)
        oop_applied = min(member_cost_share, plan.out_of_pocket_remaining_inr)
        patient_before_secondary = non_covered + member_cost_share
        if patient_before_secondary + paid != charge:
            paid = charge - patient_before_secondary
            paid = max(paid, 0)
        return {
            "allowed_amount_inr": allowed,
            "non_covered_amount_inr": non_covered,
            "deductible_applied_inr": deductible,
            "copay_inr": copay,
            "coinsurance_inr": coinsurance,
            "oop_applied_inr": oop_applied,
            "paid_inr": paid,
        }

    def _secondary_payment(
        self,
        charge_inr: int,
        claim_type: str,
        residual_inr: int,
        primary_deductible_applied_inr: int,
        secondary: Plan,
    ) -> int:
        if residual_inr <= 0:
            return 0

        deductible_credit = secondary.deductible_remaining_inr if primary_deductible_applied_inr else 0
        secondary_remaining_deductible = max(secondary.deductible_remaining_inr - deductible_credit, 0)
        covered_residual = max(residual_inr - secondary_remaining_deductible, 0)
        residual_method_payment = round(covered_residual * secondary.secondary_residual_coverage_rate)

        if secondary.secondary_coordination_method == "lesser_of":
            secondary_as_primary = self._primary_payment(charge_inr, secondary, claim_type)
            return min(residual_inr, residual_method_payment, secondary_as_primary["paid_inr"])

        return min(residual_inr, residual_method_payment)

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
            f"after {format_inr(primary_result['deductible_applied_inr'])} deductible, "
            f"{format_inr(primary_result['copay_inr'])} copay, and "
            f"{format_inr(primary_result['coinsurance_inr'])} coinsurance. "
            f"{secondary.insurer}/{secondary.label} is secondary and pays {format_inr(secondary_paid)} "
            f"toward the residual. Patient responsibility is {format_inr(patient_paid)} "
            f"on {format_inr(charge)} billed charges."
        )
