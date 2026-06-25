from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from agents.clinical_agent import ClinicalAgent
from agents.cob_agent import COBAgent
from agents.intake_agent import IntakeAgent
from agents.output_agent import OutputAgent
from utils.validation import ValidationResult


ROOT = Path(__file__).parent


class DuCOStateMachine:
    """Small agentic controller with validation and bounded repair."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "run_log": [],
            "reflection": [],
        }
        self.steps: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = [
            ("intake", IntakeAgent(ROOT / "data").run),
            ("clinical", ClinicalAgent().run),
            ("cob", COBAgent().run),
            ("output", OutputAgent(ROOT / "outputs").run),
        ]

    def run(self) -> dict[str, Any]:
        for step_name, step_fn in self.steps:
            self._transition(step_name)
            result = self._run_with_validation(step_name, step_fn)
            self.state.update(result)
        self.state["status"] = "complete"
        return self.state

    def _transition(self, step_name: str) -> None:
        self.state["current_step"] = step_name
        self.state["run_log"].append(f"ENTER:{step_name}")

    def _run_with_validation(
        self,
        step_name: str,
        step_fn: Callable[[dict[str, Any]], dict[str, Any]],
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        last_result: dict[str, Any] = {}
        for attempt in range(1, max_attempts + 1):
            last_result = step_fn(self.state)
            validation = last_result.get("validation")
            if isinstance(validation, ValidationResult):
                validation_payload = validation.to_dict()
            else:
                validation_payload = validation or {"ok": True, "issues": []}

            self.state["run_log"].append(
                f"VALIDATE:{step_name}:attempt={attempt}:ok={validation_payload['ok']}"
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


def main() -> None:
    final_state = DuCOStateMachine().run()
    print("DuCO-Agent run complete.")
    print(f"Summary: {ROOT / 'outputs' / 'summary.txt'}")
    print(f"Final JSON: {ROOT / 'outputs' / 'final_report.json'}")
    print(json.dumps({"run_log": final_state["run_log"]}, indent=2))


if __name__ == "__main__":
    main()
