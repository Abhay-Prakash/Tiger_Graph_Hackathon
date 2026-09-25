"""
High-level execution runner for the LangGraph Fraud Investigation Agent.
Supports live TigerGraph connection as well as offline/mock testing.
"""

import logging
from typing import Any, Dict, Optional
from ..policy.engine import PolicyEngine
from .graph import build_investigation_graph
from .nodes import WorkflowNodes
from .state import InvestigationState
from .mcp_client import TigerGraphMCPClient
from .tools import AgentTools

logger = logging.getLogger(__name__)


def run_fraud_investigation(
    case_data: Dict[str, Any], conn: Optional[Any] = None, live_mcp: bool = False
) -> InvestigationState:
    """
    Run a benchmark case through the LangGraph investigation workflow.

    Parameters
    ----------
    case_data : dict containing case_id, customer_id, card_id, flagged_txn_id, trigger_type, trigger_text, risk_score.
    conn      : Deprecated compatibility argument. It is never used by the agent.
    live_mcp  : ``True`` starts a real stdio MCP session; ``False`` is explicit
                offline/mock mode. The deprecated ``conn`` argument is ignored.

    Returns
    -------
    InvestigationState  — complete final state object.
    """
    mcp_client = TigerGraphMCPClient(use_mcp=live_mcp, start_session=live_mcp)
    tools = AgentTools(mcp_client=mcp_client)
    policy_engine = PolicyEngine()
    nodes = WorkflowNodes(tools=tools, policy_engine=policy_engine)
    app = build_investigation_graph(nodes)

    initial_state: InvestigationState = {
        "case_id": case_data["case_id"],
        "customer_id": case_data["customer_id"],
        "card_id": case_data.get("card_id", f"{case_data['customer_id']}-K1"),
        "flagged_txn_id": case_data["flagged_txn_id"],
        "trigger_type": case_data.get("trigger_type", "risk_score"),
        "trigger_text": case_data.get("trigger_text", ""),
        "initial_risk_score": float(case_data.get("risk_score") or 0.0),
        "opened_at": case_data.get("opened_at", ""),
        "case_status": "open",
        "exposure_usd": float(case_data.get("amount") or case_data.get("exposure_usd") or 0.0),
        "agent_trace": [],
    }

    logger.info("Starting LangGraph investigation for case %s", case_data["case_id"])
    try:
        final_state = app.invoke(initial_state)
        final_state["mcp_protocol_trace"] = list(mcp_client.protocol_trace)
        final_state["graph_transport_failures"] = list(tools.graph_transport_failures)
        if tools.graph_transport_failures:
            final_state["agent_trace"] = list(final_state.get("agent_trace", [])) + [
                "[transport] MCP graph evidence unavailable; no synthetic graph evidence was added"
            ]
        logger.info("Completed investigation for case %s. Outcome: %s", case_data["case_id"], final_state.get("outcome"))
        return final_state
    finally:
        mcp_client.close()
