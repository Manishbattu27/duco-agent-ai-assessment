from __future__ import annotations

import re
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
                clinical.update(self._clinical_only_fields(llm_result))
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
You are a medical coding reviewer for a mock insurance coordination system.
Return JSON only. Do not calculate payments.

Task:
- Interpret the parsed document text and procedure estimate.
- Respect negation. For example, "no ACL tear", "ACL intact", or "without ACL injury"
  means ACL tear is not clinically confirmed.
- Use procedure codes from the surgeon estimate when present, but do not invent a
  confirmed diagnosis unless the clinical text supports it.
- If clinical evidence is insufficient or contradictory, set
  medical_necessity_supported to false and explain why.

Required JSON keys:
- diagnosis: list of strings
- cpt_codes: list of objects with cpt and description
- icd10_codes: list of strings
- preauth_required: boolean
- medical_necessity_supported: boolean
- clinical_rationale: string

Insurance claim:

{claim}
"""
        result = optional_json_completion(prompt)
        return self._normalize_llm_result(result, claim) if result else None

    def _clinical_only_fields(self, result: dict[str, Any]) -> dict[str, Any]:
        allowed_fields = {
            "diagnosis",
            "cpt_codes",
            "icd10_codes",
            "preauth_required",
            "medical_necessity_supported",
            "clinical_rationale",
            "clinical_reference_source",
        }
        return {key: value for key, value in result.items() if key in allowed_fields}

    def _normalize_llm_result(self, result: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any] | None:
        required = {"diagnosis", "cpt_codes", "icd10_codes", "preauth_required", "clinical_rationale"}
        if not required.issubset(result):
            return None

        cpt_codes = []
        for item in result.get("cpt_codes", []):
            if isinstance(item, dict) and item.get("cpt") and item.get("description"):
                cpt_codes.append({"cpt": str(item["cpt"]), "description": str(item["description"])})
        if not cpt_codes and claim.get("procedures"):
            cpt_codes = [{"cpt": item["cpt"], "description": item["description"]} for item in claim["procedures"]]
        if not cpt_codes or not result.get("diagnosis") or not result.get("icd10_codes"):
            return None

        return {
            "diagnosis": [str(item) for item in result.get("diagnosis", [])],
            "icd10_codes": [str(item) for item in result.get("icd10_codes", [])],
            "cpt_codes": cpt_codes,
            "preauth_required": bool(result.get("preauth_required")),
            "medical_necessity_supported": bool(result.get("medical_necessity_supported", True)),
            "clinical_rationale": str(result["clinical_rationale"]),
            "clinical_reference_source": "Gemini medical coding review",
        }

    def _deterministic_inference(self, claim: dict[str, Any]) -> dict[str, Any]:
        if claim["claim_type"] == "physical_therapy":
            return {
                "diagnosis": ["Chronic low back pain"],
                "icd10_codes": ["M54.50"],
                "cpt_codes": self.CPT_KNOWLEDGE["physical_therapy"],
                "preauth_required": False,
                "medical_necessity_supported": True,
                "clinical_rationale": "PT invoice describes evaluation and therapeutic exercise for chronic back pain.",
                "clinical_reference_source": "Deterministic fallback rule set",
            }

        procedures = claim.get("procedures", self.CPT_KNOWLEDGE["surgery"])
        codes = [{"cpt": item["cpt"], "description": item["description"]} for item in procedures]
        acl_confirmed = self._has_affirmed_acl_tear(claim.get("clinical_text", ""))
        meniscus_confirmed = self._has_affirmed_meniscus_tear(claim.get("clinical_text", ""))
        diagnosis = []
        icd10_codes = []
        if acl_confirmed:
            diagnosis.append("Complete ACL tear")
            icd10_codes.append("S83.512A")
        if meniscus_confirmed:
            diagnosis.append("Medial meniscus tear")
            icd10_codes.append("S83.242A")
        if not diagnosis:
            diagnosis = ["No surgically confirmed ACL or meniscus tear in parsed MRI text"]
            icd10_codes = ["Z03.89"]

        return {
            "diagnosis": diagnosis,
            "icd10_codes": icd10_codes,
            "cpt_codes": codes,
            "preauth_required": any(item["cpt"] in self.PREAUTH_REQUIRED for item in codes),
            "medical_necessity_supported": acl_confirmed or meniscus_confirmed,
            "clinical_rationale": self._surgery_rationale(acl_confirmed, meniscus_confirmed),
            "clinical_reference_source": "Deterministic fallback rule set",
        }

    def _has_affirmed_acl_tear(self, text: str) -> bool:
        if self._has_negated_phrase(text, ("acl", "anterior cruciate ligament")):
            return False
        return bool(re.search(r"\b(complete\s+)?(acl|anterior cruciate ligament)\b.*\btear\b", text, re.I))

    def _has_affirmed_meniscus_tear(self, text: str) -> bool:
        if self._has_negated_phrase(text, ("meniscus", "meniscal")):
            return False
        return bool(re.search(r"\b(medial\s+)?menisc(?:us|al)\b.*\btear\b", text, re.I))

    def _has_negated_phrase(self, text: str, terms: tuple[str, ...]) -> bool:
        for term in terms:
            escaped = re.escape(term)
            patterns = (
                rf"\bno\s+(?:evidence\s+of\s+)?{escaped}\b.*\btear\b",
                rf"\bwithout\s+(?:.*\b)?{escaped}\b.*\btear\b",
                rf"\b{escaped}\b\s+(?:is\s+)?intact\b",
                rf"\b{escaped}\b.*\bno\s+tear\b",
            )
            if any(re.search(pattern, text, re.I) for pattern in patterns):
                return True
        return False

    def _surgery_rationale(self, acl_confirmed: bool, meniscus_confirmed: bool) -> str:
        if acl_confirmed and meniscus_confirmed:
            return "Parsed MRI text confirms ACL tear and medial meniscus tear; surgical CPTs require preauthorization."
        if acl_confirmed:
            return "Parsed MRI text confirms ACL tear; surgical CPTs require preauthorization."
        if meniscus_confirmed:
            return "Parsed MRI text confirms meniscus tear; surgical CPTs require preauthorization."
        return (
            "Parsed MRI text does not affirm an ACL or meniscus tear. CPT procedure codes may still require "
            "preauthorization, but medical necessity should be reviewed before submission."
        )

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
            auth_required_codes = any(item["cpt"] in self.PREAUTH_REQUIRED for item in claim.get("cpt_codes", []))
            if claim["claim_type"] == "surgery" and auth_required_codes and not claim.get("preauth_required"):
                issues.append("Aarav surgery should require preauthorization.")
        return ValidationResult(ok=not issues, issues=issues)
