"""
LangGraph StateGraph Workflow Compiler for Fraud Investigation Agent.

Source of truth: docs/LANGGRAPH_WORKFLOW.md
Topology: Single-orchestrator DAG with bounded conditional loop.
"""

import logging
from typing import Any, Optional
from langgraph.graph import END, START, StateGraph
from .nodes import MAX_ADDITIONAL_EVIDENCE_ROUNDS, WorkflowNodes
from .state import InvestigationState
from .tools import AgentTools

logger = logging.getLogger(__name__)


def route_sufficiency(state: InvestigationState) -> str:
    """Conditional router function for evidence_sufficiency_gate."""
    rounds = state.get("additional_evidence_rounds", 0)
    sufficient = state.get("evidence_sufficient", True)

    if not sufficient and rounds < MAX_ADDITIONAL_EVIDENCE_ROUNDS:
        return "insufficient"
    return "sufficient"


def build_investigation_graph(nodes: WorkflowNodes) -> Any:
    """
    Build and compile the LangGraph StateGraph.
    """
    workflow = StateGraph(InvestigationState)

    # Add Nodes
    workflow.add_node("initialize_case", nodes.initialize_case)
    workflow.add_node("gather_initial_evidence", nodes.gather_initial_evidence)
    workflow.add_node("retrieve_case_memory", nodes.retrieve_case_memory)
    workflow.add_node("build_evidence_ledger", nodes.build_evidence_ledger)
    workflow.add_node("assess_investigation", nodes.assess_investigation)

    # Additional Evidence Loop Nodes
    workflow.add_node("identify_missing_evidence", nodes.identify_missing_evidence)
    workflow.add_node("request_additional_evidence", nodes.request_additional_evidence)
    workflow.add_node("incorporate_response", nodes.incorporate_response)
    workflow.add_node("reassess_investigation", nodes.reassess_investigation)

    # Action & Policy Nodes
    workflow.add_node("determine_next_action", nodes.determine_next_action)
    workflow.add_node("policy_gate", nodes.policy_gate)
    workflow.add_node("approval_gate", nodes.approval_gate)
    workflow.add_node("execute_or_simulate", nodes.execute_or_simulate)
    workflow.add_node("update_case", nodes.update_case)
    workflow.add_node("write_case_memory", nodes.write_case_memory)
    workflow.add_node("generate_explanation", nodes.generate_explanation)

    # Add Edges
    workflow.add_edge(START, "initialize_case")
    workflow.add_edge("initialize_case", "gather_initial_evidence")
    workflow.add_edge("gather_initial_evidence", "retrieve_case_memory")
    workflow.add_edge("retrieve_case_memory", "build_evidence_ledger")
    workflow.add_edge("build_evidence_ledger", "assess_investigation")

    # Conditional Branch: Evidence Sufficiency Gate
    workflow.add_conditional_edges(
        "assess_investigation",
        route_sufficiency,
        {
            "insufficient": "identify_missing_evidence",
            "sufficient": "determine_next_action",
        }
    )

    # Additional Evidence Loop Connections
    workflow.add_edge("identify_missing_evidence", "request_additional_evidence")
    workflow.add_edge("request_additional_evidence", "incorporate_response")
    workflow.add_edge("incorporate_response", "reassess_investigation")
    workflow.add_edge("reassess_investigation", "determine_next_action")

    # Action & Policy Pipeline
    workflow.add_edge("determine_next_action", "policy_gate")
    workflow.add_edge("policy_gate", "approval_gate")
    workflow.add_edge("approval_gate", "execute_or_simulate")
    workflow.add_edge("execute_or_simulate", "update_case")
    workflow.add_edge("update_case", "write_case_memory")
    workflow.add_edge("write_case_memory", "generate_explanation")
    workflow.add_edge("generate_explanation", END)

    return workflow.compile()
