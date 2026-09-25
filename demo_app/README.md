# HHGOA Streamlit Analyst Console

Run the analyst console from the repository root:

```powershell
streamlit run demo_app/app.py
```

The UI loads the existing `dataset/case_pack.csv` and sends a selected case to the existing `run_fraud_investigation(..., live_mcp=True)` runner. It does not implement fraud decisions, policy evaluation, graph access, or evidence creation.

Use HHG-007 for region-contradiction visibility, HHG-001 for any actual additional-evidence branch returned by the runner, and HHG-014 for a cleared-policy outcome. Live runs upsert the existing `InvestigationCase` through the production MCP writeback path.
