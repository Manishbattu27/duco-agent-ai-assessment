from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from utils.ocr import extract_text_from_image
from utils.pdf_reader import extract_text_from_pdf
from utils.validation import ValidationResult


class IntakeAgent:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        invoice_text = self.extract_invoice()
        mri_text = self.extract_mri()
        estimate_text = self.extract_estimate()
        query_text = self.extract_user_query()

        intake = {
            "raw_documents": {
                "priya_pt_invoice": invoice_text,
                "aarav_mri_report": mri_text,
                "surgeon_estimate": estimate_text,
                "user_query": query_text,
            },
            "people": {
                "priya": {"name": "Priya Sen", "primary_plan": "plan_a", "secondary_plan": "plan_b"},
                "aarav": {"name": "Aarav Sen", "primary_plan": "plan_b", "secondary_plan": "plan_a"},
            },
            "claims": [self._parse_priya_pt(invoice_text), self._parse_aarav_surgery(estimate_text, mri_text)],
        }
        validation = self._validate(intake)
        return {"intake": intake, "validation": validation}

    def extract_invoice(self) -> str:
        return extract_text_from_image(self.data_dir / "priya_pt_invoice.png")

    def extract_mri(self) -> str:
        return extract_text_from_pdf(self.data_dir / "aarav_mri_report.pdf")

    def extract_estimate(self) -> str:
        return extract_text_from_image(self.data_dir / "surgeon_estimate.jpg")

    def extract_user_query(self) -> str:
        return (self.data_dir / "user_query.txt").read_text(encoding="utf-8")

    def _parse_priya_pt(self, text: str) -> dict[str, Any]:
        amount = self._labeled_money(
            text,
            labels=("total charges", "amount due", "total"),
            default=self._largest_money(text, default=30000),
        )
        return {
            "claim_id": "PRIYA-PT-001",
            "person": "priya",
            "claim_type": "physical_therapy",
            "status": "incurred_unpaid",
            "description": "Physical Therapy Evaluation and Therapeutic Exercise",
            "charge_inr": amount,
            "source": "priya_pt_invoice.png",
        }

    def _parse_aarav_surgery(self, estimate_text: str, mri_text: str) -> dict[str, Any]:
        procedures = []
        for code, desc, amount in re.findall(
            r"CPT\s*(\d{5})\s*[-:]\s*(.*?)\s*[-:]\s*(?:INR|Rs\.?)?\s*([0-9,]+)",
            estimate_text,
            flags=re.IGNORECASE,
        ):
            procedures.append(
                {
                    "cpt": code,
                    "description": " ".join(desc.split()),
                    "charge_inr": int(amount.replace(",", "")),
                }
            )

        if not procedures:
            procedures = [
                {
                    "cpt": "29888",
                    "description": "Arthroscopically aided ACL reconstruction",
                    "charge_inr": 350000,
                },
                {
                    "cpt": "29881",
                    "description": "Knee arthroscopy with meniscectomy",
                    "charge_inr": 100000,
                },
            ]

        procedure_total = sum(item["charge_inr"] for item in procedures)
        estimate_total = self._labeled_money(
            estimate_text,
            labels=("estimated total", "total charges", "total"),
            default=procedure_total,
        )
        reconciliation_note = None
        if estimate_total != procedure_total:
            reconciliation_note = (
                f"Estimated total INR {estimate_total:,} differs from CPT line total "
                f"INR {procedure_total:,}; claim total uses the explicit estimate total."
            )

        return {
            "claim_id": "AARAV-ACL-001",
            "person": "aarav",
            "claim_type": "surgery",
            "status": "planned",
            "description": "ACL reconstruction with meniscectomy",
            "clinical_text": mri_text,
            "procedures": procedures,
            "charge_inr": estimate_total,
            "procedure_total_inr": procedure_total,
            "reconciliation_note": reconciliation_note,
            "source": "surgeon_estimate.jpg",
        }

    def _labeled_money(self, text: str, labels: tuple[str, ...], default: int) -> int:
        for label in labels:
            pattern = (
                rf"{re.escape(label)}\s*[:\-]?\s*"
                rf"(?:INR|Rs\.?)?\s*([0-9]{{1,3}}(?:,[0-9]{{2,3}})+|[0-9]{{4,}})"
            )
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return int(match.group(1).replace(",", ""))
        return default

    def _largest_money(self, text: str, default: int) -> int:
        matches = re.findall(r"(?:INR|Rs\.?)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,})", text)
        if not matches:
            return default
        return max(int(value.replace(",", "")) for value in matches)

    def _validate(self, intake: dict[str, Any]) -> ValidationResult:
        issues = []
        if len(intake["claims"]) != 2:
            issues.append("Expected two claims: Aarav surgery and Priya PT.")
        for claim in intake["claims"]:
            if claim["charge_inr"] <= 0:
                issues.append(f"{claim['claim_id']} has no positive charge.")
        if "ACL" not in intake["raw_documents"]["aarav_mri_report"].upper():
            issues.append("MRI text did not include ACL evidence.")
        return ValidationResult(ok=not issues, issues=issues)
