from adk_duco_agent.agent import get_duco_report, list_duco_agent_traces, root_agent


def test_adk_root_agent_is_defined():
    assert root_agent is not None


def test_adk_trace_tool_returns_structured_payload():
    traces = list_duco_agent_traces()

    assert "status" in traces
    assert "router_decisions" in traces
    assert "run_log" in traces


def test_adk_report_tool_returns_structured_payload():
    report = get_duco_report()

    assert isinstance(report, dict)
    assert "status" in report or "cob" in report
