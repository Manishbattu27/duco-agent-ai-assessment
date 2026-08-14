from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ROOT / "data" / "mock_rules"


@lru_cache(maxsize=1)
def _cpt_rules() -> dict[str, list[dict[str, Any]]]:
    return json.loads((RULES_DIR / "cpt_rules.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _preauth_rules() -> dict[str, dict[str, Any]]:
    return json.loads((RULES_DIR / "preauth_rules.json").read_text(encoding="utf-8"))


def lookup_cpt_rules(claim_type: str) -> list[dict[str, str]]:
    rules = _cpt_rules().get(claim_type, [])
    return [{"cpt": str(item["cpt"]), "description": str(item["description"])} for item in rules]


def lookup_preauth_rule(cpt: str) -> dict[str, Any]:
    rule = _preauth_rules().get(str(cpt))
    if rule:
        return {
            "cpt": str(cpt),
            "preauth_required": bool(rule["preauth_required"]),
            "reason": str(rule["reason"]),
            "source": str(rule["source"]),
        }
    return {
        "cpt": str(cpt),
        "preauth_required": False,
        "reason": "No mock preauthorization rule found for this CPT.",
        "source": "Mock preauthorization rules API",
    }


def preauth_required_for_codes(cpt_codes: list[dict[str, str]]) -> bool:
    return any(lookup_preauth_rule(item["cpt"])["preauth_required"] for item in cpt_codes)
