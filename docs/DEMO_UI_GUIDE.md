# HHGOA Demo UI Guide

## Prerequisites

- Python environment with `pip install -r requirements.txt`
- `TG_HOST`, `TG_SECRET`, and `TG_GRAPHNAME=HHGOA_Fraud` configured in the existing `.env`
- A reachable TigerGraph Savanna workspace and the official `tigergraph-mcp==1.0.3` runtime
- Optional Gemini credentials. When Gemini is unavailable or rate limited, the existing runner displays its authoritative `deterministic_fallback` source.

## Launch

From the repository root:

```powershell
streamlit run demo_app/app.py
```

The console launches a real MCP session only after **Run Investigation** is selected. It never changes to offline/mock evidence after a live MCP error.

## Showcase Cases

- **HHG-007:** Review region evidence that contradicts `out_of_region_use`, the returned hypotheses, policy decision, MCP trace, and graph-memory writeback.
- **HHG-001:** Review `nba_before`, additional-evidence requests/responses, and `nba_after` when the returned workflow enters its bounded additional-evidence branch. The UI does not force this branch.
- **HHG-014:** Review the returned cleared outcome and the PolicyEngine's forbidden actions, including `BLOCK_CARD`.

## Architecture

`demo_app/adapters/runner_adapter.py` calls the existing `run_fraud_investigation(..., live_mcp=True)` function and projects its final state for Streamlit. Components render the returned ledger, policy decision, trace, MCP protocol events, and writeback event. The UI does not call TigerGraph directly or implement fraud/policy logic.

## Known Limitations

- Each run is a real investigation and performs the existing MCP `InvestigationCase` writeback.
- The benchmark pack does not supply an amount field to the runner, so its recorded `exposure_usd` can be zero.
- Gemini quota or availability issues remain visible as `deterministic_fallback`; they are not hidden by the UI.
- If MCP is unavailable, the UI presents the returned transport failure and does not create substitute graph evidence.

## Troubleshooting

- **Case pack missing:** Restore the local `dataset/` directory required by the frozen evaluation environment.
- **MCP unavailable:** Verify `TG_HOST`, `TG_SECRET`, `TG_GRAPHNAME`, workspace availability, and `tigergraph-mcp` installation.
- **No evidence returned:** Expand **Technical Trace** and inspect `graph_transport_failures` before retrying.
- **Gemini 429:** The returned deterministic fallback is expected behavior; inspect its reasoning source in the case overview and technical trace.
