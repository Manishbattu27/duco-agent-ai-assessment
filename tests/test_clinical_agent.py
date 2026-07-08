from agents.clinical_agent import ClinicalAgent


def _surgery_claim(clinical_text: str) -> dict:
    return {
        "claim_id": "AARAV-ACL-001",
        "person": "aarav",
        "claim_type": "surgery",
        "description": "ACL reconstruction with meniscectomy",
        "clinical_text": clinical_text,
        "procedures": [
            {"cpt": "29888", "description": "ACL reconstruction", "charge_inr": 350000},
            {"cpt": "29881", "description": "Meniscectomy", "charge_inr": 100000},
        ],
        "charge_inr": 450000,
    }


def test_deterministic_clinical_fallback_respects_no_acl_tear():
    agent = ClinicalAgent()
    result = agent._deterministic_inference(
        _surgery_claim("MRI knee report: ACL is intact. No ACL tear identified. Menisci are preserved.")
    )

    assert "Complete ACL tear" not in result["diagnosis"]
    assert result["medical_necessity_supported"] is False
    assert result["preauth_required"] is True
    assert "reviewed before submission" in result["clinical_rationale"]


def test_deterministic_clinical_fallback_affirms_acl_and_meniscus_tears():
    agent = ClinicalAgent()
    result = agent._deterministic_inference(
        _surgery_claim("MRI confirms complete ACL tear with medial meniscus tear.")
    )

    assert "Complete ACL tear" in result["diagnosis"]
    assert "Medial meniscus tear" in result["diagnosis"]
    assert result["medical_necessity_supported"] is True
