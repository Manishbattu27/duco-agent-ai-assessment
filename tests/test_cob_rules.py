from utils.insurance_rules import COBRulesEngine


def test_aarav_surgery_cob_balances_to_charge():
    claim = {
        "claim_id": "AARAV-ACL-001",
        "person": "aarav",
        "claim_type": "surgery",
        "description": "ACL reconstruction with meniscectomy",
        "charge_inr": 450000,
        "diagnosis": ["Complete ACL tear", "Medial meniscus tear"],
        "cpt_codes": [{"cpt": "29888", "description": "ACL reconstruction"}],
        "preauth_required": True,
    }
    result = COBRulesEngine().adjudicate_claim(claim)

    assert result["primary_plan"] == "plan_b"
    assert result["secondary_plan"] == "plan_a"
    assert result["primary_paid_inr"] == 336000
    assert result["secondary_paid_inr"] == 114000
    assert result["patient_paid_inr"] == 0
    assert result["primary_paid_inr"] + result["secondary_paid_inr"] == 450000


def test_priya_pt_cob_balances_to_charge():
    claim = {
        "claim_id": "PRIYA-PT-001",
        "person": "priya",
        "claim_type": "physical_therapy",
        "description": "Physical Therapy Evaluation and Therapeutic Exercise",
        "charge_inr": 30000,
        "diagnosis": ["Chronic low back pain"],
        "cpt_codes": [{"cpt": "97161", "description": "PT evaluation"}],
        "preauth_required": False,
    }
    result = COBRulesEngine().adjudicate_claim(claim)

    assert result["primary_plan"] == "plan_a"
    assert result["secondary_plan"] == "plan_b"
    assert result["primary_paid_inr"] == 18000
    assert result["secondary_paid_inr"] == 12000
    assert result["patient_paid_inr"] == 0
