from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse


def ui_token_required() -> bool:
    return bool(os.getenv("DUCO_UI_TOKEN"))


def request_has_valid_token(path: str, headers: object, form: dict[str, str] | None = None) -> bool:
    expected = os.getenv("DUCO_UI_TOKEN")
    if not expected:
        return True

    header_token = getattr(headers, "get", lambda _key, _default=None: None)("X-Duco-Token")
    query_token = parse_qs(urlparse(path).query).get("token", [""])[0]
    form_token = (form or {}).get("token", "")
    return expected in {header_token, query_token, form_token}
