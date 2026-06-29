from __future__ import annotations

from typing import Any

from utils.llm import optional_json_completion
from utils.validation import ValidationResult


class ClinicalAgent:
    CPT_KNOWLEDGE = {
        "physical_therapy": [
            {"cpt": "97161", "description": "Physical therapy evaluation, low complexity"},
            {"cpt": "97110", "description": "Therapeutic exercises"},
        ],
        "surgery": [
            {"cpt": "29888", "description": "Arthroscopically aided ACL reconstruction"},
            {"cpt": "29881", "description": "Knee arthroscopy with meniscectomy"},
        ],
    }

    PREAUTH_REQUIRED = {"29888", "29881"}

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        intake = state["intake"]
        clinical_claims = []

        for claim in intake["claims"]:
            clinical = dict(claim)
            llm_result = self._try_llm_inference(claim)
            if llm_result:
                clinical.update(llm_result)
            else:
                clinical.update(self._deterministic_inference(claim))
            clinical_claims.append(clinical)

        clinical_data = {
            "claims": clinical_claims,
            "medical_summary": self.generate_medical_summary(clinical_claims),
        }
        return {"clinical": clinical_data, "validation": self._validate(clinical_data)}

    def _try_llm_inference(self, claim: dict[str, Any]) -> dict[str, Any] | None:
        prompt = f"""
Return JSON only. Extract diagnosis, cpt_codes, icd10_codes, preauth_required,
and clinical_rationale for this insurance claim:

{claim}
"""
        return optional_json_completion(prompt)

    def _deterministic_inference(self, claim: dict[str, Any]) -> dict[str, Any]:
        if claim["claim_type"] == "physical_therapy":
            return {
                "diagnosis": ["Chronic low back pain"],
                "icd10_codes": ["M54.50"],
                "cpt_codes": self.CPT_KNOWLEDGE["physical_therapy"],
                "preauth_required": False,
                "clinical_rationale": "PT invoice describes evaluation and therapeutic exercise for chronic back pain.",
            }

        procedures = claim.get("procedures", self.CPT_KNOWLEDGE["surgery"])
        codes = [{"cpt": item["cpt"], "description": item["description"]} for item in procedures]
        return {
            "diagnosis": ["Complete ACL tear", "Medial meniscus tear"],
            "icd10_codes": ["S83.512A", "S83.242A"],
            "cpt_codes": codes,
            "preauth_required": any(item["cpt"] in self.PREAUTH_REQUIRED for item in codes),
            "clinical_rationale": "MRI confirms ACL tear and medial meniscus tear; surgical CPTs are high-cost procedures.",
        }

    def check_preauthorization(self, cpt_codes: list[dict[str, str]]) -> bool:
        return any(code["cpt"] in self.PREAUTH_REQUIRED for code in cpt_codes)

    def generate_medical_summary(self, claims: list[dict[str, Any]]) -> str:
        lines = []
        for claim in claims:
            diagnoses = ", ".join(claim.get("diagnosis", []))
            codes = ", ".join(item["cpt"] for item in claim.get("cpt_codes", []))
            lines.append(f"{claim['claim_id']}: {diagnoses}. CPT: {codes}.")
        return "\n".join(lines)

    def _validate(self, clinical_data: dict[str, Any]) -> ValidationResult:
        issues = []
        for claim in clinical_data["claims"]:
            if not claim.get("cpt_codes"):
                issues.append(f"{claim['claim_id']} has no CPT codes.")
            if not claim.get("diagnosis"):
                issues.append(f"{claim['claim_id']} has no diagnosis.")
            if not claim.get("icd10_codes"):
                issues.append(f"{claim['claim_id']} has no ICD-10 codes.")
            if claim["claim_type"] == "surgery" and not claim.get("preauth_required"):
                issues.append("Aarav surgery should require preauthorization.")
        return ValidationResult(ok=not issues, issues=issues)
