from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any


def optional_json_completion(prompt: str) -> dict[str, Any] | None:
    """Use Gemini when configured; otherwise return None for deterministic fallback."""
    _load_local_env()
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.removeprefix("json").strip()
        return json.loads(text)
    except Exception:
        return None


def optional_vision_text_extraction(path: Path, document_type: str) -> str | None:
    """Use Gemini Vision as an optional OCR/metadata fallback for uploaded images."""
    _load_local_env()
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            import google.generativeai as genai
            from PIL import Image

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        model = genai.GenerativeModel(model_name)
        prompt = f"""
Extract raw readable text and key billing metadata from this {document_type}.
Return plain text only. Include patient name, service descriptions, CPT codes,
dates, and INR amounts when visible. Do not calculate insurance payments.
"""
        response = model.generate_content([prompt, Image.open(path)])
        text = response.text.strip()
        return text or None
    except Exception:
        return None


def optional_judge_validation(step_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Optional LLM judge for workflow validation. It never replaces deterministic validation."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    prompt = f"""
You are a strict validation judge for a mock health insurance agent workflow.
Review this {step_name} output for obvious missing fields, unsafe assumptions,
or contradictions. Do not calculate claim payments.

Return JSON only:
{{
  "ok": true or false,
  "issues": ["short issue strings"],
  "rationale": "short reason"
}}

Payload:
{json.dumps(payload, ensure_ascii=False, default=str)}
"""
    result = optional_json_completion(prompt)
    if not isinstance(result, dict) or "ok" not in result:
        return None
    return {
        "ok": bool(result.get("ok")),
        "issues": [str(item) for item in result.get("issues", [])],
        "rationale": str(result.get("rationale", "")),
    }


def _load_local_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        return
