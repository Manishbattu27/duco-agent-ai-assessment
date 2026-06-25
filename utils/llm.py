from __future__ import annotations

import json
import os
from typing import Any


def optional_json_completion(prompt: str) -> dict[str, Any] | None:
    """Use Gemini when configured; otherwise return None for deterministic fallback."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.removeprefix("json").strip()
        return json.loads(text)
    except Exception:
        return None
