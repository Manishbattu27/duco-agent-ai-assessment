from utils.mock_apis import lookup_cpt_rules, lookup_preauth_rule, preauth_required_for_codes


def test_mock_cpt_rules_are_loaded_from_json_database():
    pt_codes = lookup_cpt_rules("physical_therapy")

    assert {"cpt": "97161", "description": "Physical therapy evaluation, low complexity"} in pt_codes
    assert {"cpt": "97110", "description": "Therapeutic exercises"} in pt_codes


def test_mock_preauth_rules_are_loaded_from_json_database():
    surgery_rule = lookup_preauth_rule("29888")
    pt_rule = lookup_preauth_rule("97110")

    assert surgery_rule["preauth_required"] is True
    assert pt_rule["preauth_required"] is False
    assert preauth_required_for_codes([{"cpt": "29888", "description": "ACL"}]) is True
