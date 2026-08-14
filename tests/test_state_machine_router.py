from main import DuCOStateMachine
from utils.validation import ValidationResult


def test_state_machine_records_router_decisions():
    state = DuCOStateMachine().run()

    decisions = state["router_decisions"]

    assert [decision["step"] for decision in decisions] == ["intake", "clinical", "cob", "output"]
    assert all(decision["action"] == "run" for decision in decisions)
    assert decisions[0]["required_state"] == []
    assert decisions[-1]["required_state"] == ["intake", "clinical", "cob"]


def test_state_machine_skips_downstream_steps_after_validation_failure():
    machine = DuCOStateMachine()
    calls = []

    def failed_intake(_state):
        calls.append("intake")
        return {"intake": {"claims": []}, "validation": ValidationResult(False, ["bad intake"])}

    def downstream_step(name):
        def _step(_state):
            calls.append(name)
            return {name: {}, "validation": ValidationResult(True, [])}

        return _step

    machine.steps = [
        ("intake", failed_intake),
        ("clinical", downstream_step("clinical")),
        ("cob", downstream_step("cob")),
        ("output", downstream_step("output")),
    ]

    state = machine.run()

    assert state["status"] == "failed"
    assert calls == ["intake", "intake"]
    assert state["error"]["type"] == "ValidationFailure"
    assert [decision["action"] for decision in state["router_decisions"]] == ["run", "skip", "skip", "skip"]
    assert [decision["step"] for decision in state["router_decisions"][1:]] == ["clinical", "cob", "output"]
