from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": event_type,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
