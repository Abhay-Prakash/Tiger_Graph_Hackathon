"""Focused tests for the production MCP transport boundary."""

import json
from types import SimpleNamespace

from fraud_investigation.agent.mcp_client import TigerGraphMCPClient
from fraud_investigation.agent.tools import AgentTools


class FakeMCPTransport:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []
        self.started = False
        self.closed = False

    def start(self):
        self.started = True
        return ["tigergraph__run_installed_query", "tigergraph__add_nodes"]

    def call(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


class UnavailableMCPTransport(FakeMCPTransport):
    def start(self):
        raise RuntimeError("controlled MCP outage")


def result(payload, is_error=False):
    text = "```json\n" + json.dumps(payload) + "\n```"
    return SimpleNamespace(content=[SimpleNamespace(text=text)], isError=is_error)


def test_real_mcp_session_records_initialize_list_and_call():
    transport = FakeMCPTransport([
        result({"success": True, "data": {"result": [{"FlaggedTxn": [{"v_id": "3514948"}]}]}})
    ])
    client = TigerGraphMCPClient(transport=transport, start_session=True)

    data = client.run_query_get_transaction_context("3514948", 90)

    assert transport.started
    assert transport.calls[0][0] == "tigergraph__run_installed_query"
    assert transport.calls[0][1]["params"]["lookback_days"] == 90
    assert data["FlaggedTxn"][0]["v_id"] == "3514948"
    assert [event["event"] for event in client.protocol_trace] == ["initialize", "tools/list", "tools/call"]


def test_explicit_offline_mode_does_not_start_mcp():
    client = TigerGraphMCPClient(use_mcp=False, start_session=True)

    assert client.transport_name == "mock_mcp"
    assert client.is_live() is False

    evidence = AgentTools(mcp_client=client).fetch_transaction_context("3514030")
    assert len(evidence) == 1
    assert evidence[0].observed_value["transport"] == "mock_mcp"


def test_runner_ignores_deprecated_connection_when_mode_is_offline(monkeypatch):
    from fraud_investigation.agent import runner
    from fraud_investigation.agent.llm_reasoner import LLMReasoner

    captured = {}
    original_client = runner.TigerGraphMCPClient

    class CapturingClient(original_client):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(runner, "TigerGraphMCPClient", CapturingClient)
    monkeypatch.setattr(
        LLMReasoner,
        "_call_llm_json",
        lambda self, prompt: (_ for _ in ()).throw(RuntimeError("test fallback")),
    )
    runner.run_fraud_investigation(
        {"case_id": "HHG-MODE", "customer_id": "C1", "flagged_txn_id": "T1", "risk_score": 0.1},
        conn=object(),
        live_mcp=False,
    )

    assert captured["use_mcp"] is False
    assert captured["start_session"] is False


def test_mcp_error_is_structured_and_never_falls_back_to_a_connection():
    transport = FakeMCPTransport([result({"success": False, "error": "server rejected query"})])
    client = TigerGraphMCPClient(transport=transport, start_session=True)

    response = client.call_mcp_tool("run_installed_query", {"query_name": "get_transaction_context", "params": {}})

    assert response["success"] is False
    assert client.last_call_succeeded is False
    assert transport.calls[0][0] == "tigergraph__run_installed_query"


def test_live_mcp_failure_does_not_fabricate_graph_evidence():
    transport = FakeMCPTransport([result({"success": False, "error": "server rejected query"})])
    client = TigerGraphMCPClient(transport=transport, start_session=True)
    tools = AgentTools(mcp_client=client)

    evidence = tools.fetch_transaction_context("3514948")

    assert evidence == []
    assert tools.graph_transport_failures == [{
        "operation": "get_transaction_context",
        "transport": "stdio_mcp",
        "error": "server rejected query",
    }]


def test_unavailable_live_mcp_does_not_reach_benchmark_region_fixture():
    client = TigerGraphMCPClient(transport=UnavailableMCPTransport(), start_session=True)
    tools = AgentTools(mcp_client=client)

    evidence = tools.fetch_region_anomaly("C09933", "3514948")

    assert client.transport_name == "MCP_UNAVAILABLE"
    assert evidence == []
    assert tools.graph_transport_failures[0]["operation"] == "detect_region_anomaly"


def test_empty_mcp_query_result_is_safe():
    transport = FakeMCPTransport([result({"success": True, "data": {"result": []}})])
    client = TigerGraphMCPClient(transport=transport, start_session=True)

    assert client.run_query_detect_shared_device("3514948") == {}
    assert client.last_call_succeeded is True


def test_case_write_uses_discovered_add_nodes_tool():
    transport = FakeMCPTransport([result({"success": True, "data": {"success_count": 1}})])
    client = TigerGraphMCPClient(transport=transport, start_session=True)

    response = client.call_mcp_tool("upsert_vertices", {
        "vertex_type": "InvestigationCase",
        "vertices": [("MCP-TRANSPORT-TEST-001", {"outcome": "pending"})],
    })

    assert response["success"] is True
    tool_name, arguments = transport.calls[0]
    assert tool_name == "tigergraph__add_nodes"
    assert arguments["vertex_id"] == "case_id"
    assert arguments["vertices"] == [{"case_id": "MCP-TRANSPORT-TEST-001", "outcome": "pending"}]
