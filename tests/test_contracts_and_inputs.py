import pytest

from utils.contracts import validate_contract
from web_app import _amount_from_payload


def test_contract_validation_detects_missing_fields():
    result = validate_contract("cob_agent", {"claims": []})

    assert not result.ok
    assert "total_charges_inr" in " ".join(result.issues)


def test_amount_parser_rejects_non_digits():
    with pytest.raises(ValueError):
        _amount_from_payload({"pt_amount": "40k"}, "pt_amount")


def test_amount_parser_accepts_comma_format():
    assert _amount_from_payload({"pt_amount": "40,000"}, "pt_amount") == 40000
