from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from main import DuCOStateMachine


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"


def run_duco_analysis() -> dict[str, Any]:
    """Run the full DuCO-Agent workflow and return structured results."""
    state = DuCOStateMachine().run()
    report = _read_final_report()
    cob = report.get("cob", {}) if report else {}
    return {
        "status": state.get("status"),
        "run_id": state.get("run_id"),
        "total_charges_inr": cob.get("total_charges_inr"),
        "total_insurer_paid_inr": cob.get("total_insurer_paid_inr"),
        "household_out_of_pocket_inr": cob.get("household_out_of_pocket_inr"),
        "router_decisions": state.get("router_decisions", []),
        "run_log": state.get("run_log", []),
    }


def get_duco_report() -> dict[str, Any]:
    """Return the latest machine-readable DuCO final report."""
    report = _read_final_report()
    if not report:
        return {
            "status": "missing",
            "message": "No final report exists yet. Run run_duco_analysis first.",
        }
    return report


def list_duco_agent_traces() -> dict[str, Any]:
    """Return router decisions and run log entries for agent trace review."""
    report = _read_final_report()
    if not report:
        return {
            "status": "missing",
            "router_decisions": [],
            "run_log": [],
            "message": "No trace data exists yet. Run run_duco_analysis first.",
        }
    return {
        "status": report.get("status", "unknown"),
        "run_id": report.get("run_id"),
        "router_decisions": report.get("router_decisions", []),
        "run_log": report.get("run_log", []),
        "reflection": report.get("reflection", []),
    }


def _read_final_report() -> dict[str, Any] | None:
    path = OUTPUT_DIR / "final_report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


try:
    from google.adk.agents import Agent
except Exception:
    Agent = None  # type: ignore[assignment]


if Agent is not None:
    root_agent = Agent(
        name="duco_agent",
        model="gemini-2.5-flash",
        description="Coordinates dual health insurance benefits for Priya and Aarav Sen.",
        instruction=(
            "You are DuCO-Agent, a coordination-of-benefits assistant. "
            "Use the provided tools to run the deterministic workflow, inspect the final report, "
            "and explain the agent trace. Do not invent claim payments; payment calculations must "
            "come from the run_duco_analysis or get_duco_report tool outputs."
        ),
        tools=[run_duco_analysis, get_duco_report, list_duco_agent_traces],
    )
else:
    root_agent = {
        "name": "duco_agent",
        "framework": "google-adk",
        "status": "google-adk package not installed in this environment",
        "tools": ["run_duco_analysis", "get_duco_report", "list_duco_agent_traces"],
    }
