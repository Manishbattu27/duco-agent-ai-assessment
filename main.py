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
from utils.llm import optional_judge_validation
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
            "router_decisions": [],
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
            for index, (step_name, step_fn) in enumerate(self.steps):
                decision = self._route_decision(step_name)
                self.state["router_decisions"].append(decision)
                self.audit.record(
                    "router_decision",
                    step=step_name,
                    action=decision["action"],
                    reason=decision["reason"],
                    required_state=decision["required_state"],
                )
                if decision["action"] == "skip":
                    self.state["run_log"].append(
                        {
                            "timestamp": utc_now(),
                            "event": "skip_step",
                            "step": step_name,
                            "reason": decision["reason"],
                        }
                    )
                    continue
                self._transition(step_name, decision)
                result = self._run_with_validation(step_name, step_fn)
                self.state.update(result)
                validation = result.get("validation", {"ok": True, "issues": []})
                if not validation.get("ok", True):
                    return self._stop_after_validation_failure(step_name, validation, self.steps[index + 1 :])
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

    def _route_decision(self, step_name: str) -> dict[str, Any]:
        prerequisites = self._required_state_for_step(step_name)
        missing = [key for key in prerequisites if key not in self.state]
        if missing:
            return {
                "timestamp": utc_now(),
                "step": step_name,
                "action": "skip",
                "reason": f"Missing prerequisite state: {', '.join(missing)}.",
                "required_state": prerequisites,
            }

        reasons = {
            "intake": "Source documents or manual values may have changed; extract fresh structured claims.",
            "clinical": "Structured claims are available; enrich them with diagnosis, CPT, ICD-10, and preauthorization data.",
            "cob": "Clinically enriched claims are available; calculate primary, secondary, and patient payment responsibility.",
            "output": "Validated intake, clinical, and COB results are available; generate patient and insurer deliverables.",
        }
        return {
            "timestamp": utc_now(),
            "step": step_name,
            "action": "run",
            "reason": reasons[step_name],
            "required_state": prerequisites,
        }

    def _transition(self, step_name: str, decision: dict[str, Any]) -> None:
        self.state["current_step"] = step_name
        event = {
            "timestamp": utc_now(),
            "event": "enter_step",
            "step": step_name,
            "router_reason": decision["reason"],
        }
        self.state["run_log"].append(event)
        self.audit.record("enter_step", step=step_name, router_reason=decision["reason"])

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

            judge_result = optional_judge_validation(step_name, last_result)
            if judge_result:
                judge_event = {
                    "timestamp": utc_now(),
                    "event": "llm_judge_validation",
                    "step": step_name,
                    "attempt": attempt,
                    "ok": judge_result["ok"],
                    "issues": judge_result["issues"],
                    "rationale": judge_result["rationale"],
                }
                self.state["run_log"].append(judge_event)
                self.audit.record(
                    "llm_judge_validation",
                    step=step_name,
                    attempt=attempt,
                    ok=judge_result["ok"],
                    issues=judge_result["issues"],
                    rationale=judge_result["rationale"],
                )
                if not judge_result["ok"]:
                    self.state["reflection"].append(
                        {
                            "step": step_name,
                            "attempt": attempt,
                            "issues": [f"LLM judge: {issue}" for issue in judge_result["issues"]],
                            "repair_action": "Recorded advisory LLM judge concerns; deterministic validation remains authoritative.",
                        }
                    )

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
        return last_result

    def _stop_after_validation_failure(
        self,
        failed_step: str,
        validation: dict[str, Any],
        remaining_steps: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]],
    ) -> dict[str, Any]:
        self.state["status"] = "failed"
        self.state["completed_at"] = utc_now()
        self.state["error"] = {
            "type": "ValidationFailure",
            "message": f"{failed_step} failed validation; downstream agents were skipped.",
            "issues": validation.get("issues", []),
        }
        self.audit.record("run_failed", status="failed", error=self.state["error"])
        for step_name, _step_fn in remaining_steps:
            reason = f"Skipped because upstream step '{failed_step}' failed validation."
            decision = {
                "timestamp": utc_now(),
                "step": step_name,
                "action": "skip",
                "reason": reason,
                "required_state": self._required_state_for_step(step_name),
            }
            self.state["router_decisions"].append(decision)
            self.state["run_log"].append(
                {
                    "timestamp": utc_now(),
                    "event": "skip_step",
                    "step": step_name,
                    "reason": reason,
                }
            )
            self.audit.record(
                "router_decision",
                step=step_name,
                action="skip",
                reason=reason,
                required_state=decision["required_state"],
            )
        self._refresh_final_report()
        return self.state

    def _required_state_for_step(self, step_name: str) -> list[str]:
        return {
            "intake": [],
            "clinical": ["intake"],
            "cob": ["clinical"],
            "output": ["intake", "clinical", "cob"],
        }[step_name]

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
        report["router_decisions"] = self.state.get("router_decisions", [])
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
