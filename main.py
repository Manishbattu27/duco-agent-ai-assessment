from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from agents.clinical_agent import ClinicalAgent
from agents.cob_agent import COBAgent
from agents.intake_agent import IntakeAgent
from agents.output_agent import OutputAgent
from utils.audit import AuditLogger, utc_now
from utils.contracts import TOOL_CONTRACTS, validate_contract
from utils.validation import ValidationResult


ROOT = Path(__file__).parent


class DuCOStateMachine:
    """Small agentic controller with validation and bounded repair."""

    def __init__(self) -> None:
        run_id = str(uuid.uuid4())
        self.state: dict[str, Any] = {
            "run_id": run_id,
            "status": "running",
            "started_at": utc_now(),
            "run_log": [],
            "reflection": [],
            "tool_contracts": TOOL_CONTRACTS,
        }
        self.audit = AuditLogger(ROOT / "outputs" / "audit_log.jsonl", run_id)
        self.steps: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = [
            ("intake", IntakeAgent(ROOT / "data").run),
            ("clinical", ClinicalAgent().run),
            ("cob", COBAgent().run),
            ("output", OutputAgent(ROOT / "outputs").run),
        ]

    def run(self) -> dict[str, Any]:
        self.audit.record("run_started", status="running")
        try:
            for step_name, step_fn in self.steps:
                self._transition(step_name)
                result = self._run_with_validation(step_name, step_fn)
                self.state.update(result)
            self.state["status"] = "complete"
            self.state["completed_at"] = utc_now()
            self.audit.record("run_completed", status="complete")
            self._refresh_final_report()
            return self.state
        except Exception as exc:
            self.state["status"] = "failed"
            self.state["completed_at"] = utc_now()
            self.state["error"] = {"type": exc.__class__.__name__, "message": str(exc)}
            self.audit.record("run_failed", status="failed", error=self.state["error"])
            self._refresh_final_report()
            raise

    def _transition(self, step_name: str) -> None:
        self.state["current_step"] = step_name
        event = {"timestamp": utc_now(), "event": "enter_step", "step": step_name}
        self.state["run_log"].append(event)
        self.audit.record("enter_step", step=step_name)

    def _run_with_validation(
        self,
        step_name: str,
        step_fn: Callable[[dict[str, Any]], dict[str, Any]],
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        last_result: dict[str, Any] = {}
        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            last_result = step_fn(self.state)
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            validation = last_result.get("validation")
            if isinstance(validation, ValidationResult):
                validation_payload = validation.to_dict()
            else:
                validation_payload = validation or {"ok": True, "issues": []}

            result_key = next((key for key in last_result if key != "validation"), "")
            contract_validation = self._validate_contract_for_step(step_name, result_key, last_result)
            if not contract_validation["ok"]:
                validation_payload["ok"] = False
                validation_payload["issues"].extend(contract_validation["issues"])

            event = {
                "timestamp": utc_now(),
                "event": "validate_step",
                "step": step_name,
                "attempt": attempt,
                "ok": validation_payload["ok"],
                "duration_ms": duration_ms,
                "issues": validation_payload["issues"],
            }
            self.state["run_log"].append(event)
            self.audit.record(
                "validate_step",
                step=step_name,
                attempt=attempt,
                ok=validation_payload["ok"],
                duration_ms=duration_ms,
                issues=validation_payload["issues"],
            )
            if validation_payload["ok"]:
                last_result["validation"] = validation_payload
                return last_result

            self.state["reflection"].append(
                {
                    "step": step_name,
                    "attempt": attempt,
                    "issues": validation_payload["issues"],
                    "repair_action": "Retrying with deterministic fallback parsing/rules.",
                }
            )

        last_result["validation"] = {
            "ok": False,
            "issues": [f"{step_name} failed validation after {max_attempts} attempts"],
        }
        raise RuntimeError(json.dumps(last_result["validation"], indent=2))

    def _validate_contract_for_step(
        self,
        step_name: str,
        result_key: str,
        last_result: dict[str, Any],
    ) -> dict[str, Any]:
        contract_name = f"{step_name}_agent"
        if contract_name not in TOOL_CONTRACTS or result_key not in last_result:
            return {"ok": True, "issues": []}
        return validate_contract(contract_name, last_result[result_key]).to_dict()

    def _refresh_final_report(self) -> None:
        report_path = ROOT / "outputs" / "final_report.json"
        if not report_path.exists():
            return
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["run_id"] = self.state["run_id"]
        report["status"] = self.state["status"]
        report["started_at"] = self.state["started_at"]
        report["completed_at"] = self.state.get("completed_at")
        report["tool_contracts"] = self.state["tool_contracts"]
        if "error" in self.state:
            report["error"] = self.state["error"]
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    final_state = DuCOStateMachine().run()
    print("DuCO-Agent run complete.")
    print(f"Summary: {ROOT / 'outputs' / 'summary.txt'}")
    print(f"Final JSON: {ROOT / 'outputs' / 'final_report.json'}")
    print(json.dumps({"run_log": final_state["run_log"]}, indent=2))


if __name__ == "__main__":
    main()
