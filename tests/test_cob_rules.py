from utils.insurance_rules import COBRulesEngine, Plan


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
    assert result["allowed_amount_inr"] == 450000
    assert result["primary_copay_inr"] == 0
    assert result["non_covered_amount_inr"] == 0


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


def test_primary_payment_models_allowed_amount_copay_and_oop_cap():
    plans = {
        "plan_a": Plan(
            id="plan_a",
            label="Plan A",
            insurer="Insurer1",
            deductible_remaining_inr=5000,
            coinsurance_rate=0.20,
            secondary_residual_coverage_rate=0.0,
            out_of_pocket_remaining_inr=10000,
            allowed_amount_rate=0.80,
            copay_by_claim_type={"physical_therapy": 1000},
        ),
        "plan_b": Plan(
            id="plan_b",
            label="Plan B",
            insurer="Insurer2",
            deductible_remaining_inr=0,
            coinsurance_rate=0.0,
            secondary_residual_coverage_rate=0.0,
        ),
    }
    claim = {
        "claim_id": "PRIYA-PT-TEST",
        "person": "priya",
        "claim_type": "physical_therapy",
        "description": "PT",
        "charge_inr": 50000,
        "diagnosis": ["Back pain"],
        "cpt_codes": [{"cpt": "97110", "description": "Exercise"}],
        "preauth_required": False,
    }

    result = COBRulesEngine(plans=plans).adjudicate_claim(claim)

    assert result["allowed_amount_inr"] == 40000
    assert result["non_covered_amount_inr"] == 10000
    assert result["primary_deductible_applied_inr"] == 5000
    assert result["primary_copay_inr"] == 1000
    assert result["primary_oop_applied_inr"] == 10000
    assert result["primary_paid_inr"] == 30000
    assert result["patient_paid_inr"] == 20000


def test_secondary_lesser_of_coordination_caps_payment():
    plans = {
        "plan_a": Plan(
            id="plan_a",
            label="Plan A",
            insurer="Insurer1",
            deductible_remaining_inr=10000,
            coinsurance_rate=0.50,
            secondary_residual_coverage_rate=1.0,
        ),
        "plan_b": Plan(
            id="plan_b",
            label="Plan B",
            insurer="Insurer2",
            deductible_remaining_inr=0,
            coinsurance_rate=0.90,
            secondary_residual_coverage_rate=1.0,
            secondary_coordination_method="lesser_of",
        ),
    }
    claim = {
        "claim_id": "PRIYA-PT-TEST",
        "person": "priya",
        "claim_type": "physical_therapy",
        "description": "PT",
        "charge_inr": 100000,
        "diagnosis": ["Back pain"],
        "cpt_codes": [{"cpt": "97110", "description": "Exercise"}],
        "preauth_required": False,
    }

    result = COBRulesEngine(plans=plans).adjudicate_claim(claim)

    assert result["primary_paid_inr"] == 45000
    assert result["secondary_paid_inr"] == 10000
    assert result["patient_paid_inr"] == 45000
