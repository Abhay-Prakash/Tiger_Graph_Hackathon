from demo_app.adapters.runner_adapter import case_by_id, present_state, run_live_case


def _state():
    return {
        "case_id": "HHG-007",
        "customer_id": "C09933",
        "card_id": "C09933-K1",
        "flagged_txn_id": "3514948",
        "trigger_type": "risk_score",
        "initial_risk_score": 0.87,
        "outcome": "confirmed_fraud",
        "pattern": "card_testing",
        "reasoning_source": "deterministic_fallback",
        "evidence_ledger_json": "[]",
        "agent_trace": ["[00:00:00] [write_case_memory] Persisted case HHG-007 resolution to graph via MCP"],
        "mcp_protocol_trace": [{"event": "tools/call", "tool": "tigergraph__add_nodes"}],
        "policy_decision": {"forbidden_actions": ["CLOSE_NO_FRAUD"], "required_actions": ["CREATE_CASE", "BLOCK_CARD"]},
        "executed_actions": ["CREATE_CASE", "BLOCK_CARD"],
    }


def test_present_state_uses_runner_output_for_writeback_and_policy_display():
    view = present_state(_state())

    assert view["graph_memory"]["writeback_observed_via_mcp"] is True
    assert view["policy"]["reported_violations"] == []
    assert view["timeline"][0]["label"] == "Case Writeback"


def test_run_live_case_forces_existing_runner_into_live_mcp_mode():
    calls = []

    def runner(case, live_mcp):
        calls.append((case, live_mcp))
        return _state()

    view = run_live_case({"case_id": "HHG-007"}, runner=runner)

    assert calls == [({"case_id": "HHG-007"}, True)]
    assert view["case"]["case_id"] == "HHG-007"


def test_case_by_id_returns_existing_case_without_ui_fixture_data():
    case = {"case_id": "HHG-014"}
    assert case_by_id("HHG-014", [case]) is case
