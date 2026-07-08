from __future__ import annotations

import json
import os
import warnings
from typing import Any


def optional_json_completion(prompt: str) -> dict[str, Any] | None:
    """Use Gemini when configured; otherwise return None for deterministic fallback."""
    _load_local_env()
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


def _load_local_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        return
