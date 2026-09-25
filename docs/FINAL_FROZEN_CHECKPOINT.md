# HHGOA Final Frozen Checkpoint

## Checkpoint

- Timestamp: `2026-09-25T17:35:36+05:30`
- Git HEAD at audit: `e3367cfbeac073f0f623a5ca140d4432a5fc9e1d`
- Working tree: baseline implementation changes are uncommitted; `dataset/`, `Documents/`, and root `tests/` remain untracked local materials and are excluded from the checkpoint commit.
- Temporary cleanup: removed only `InvestigationCase:HHG-TEST-MEM` using real MCP tool `tigergraph__delete_node` with `graph_name=HHGOA_Fraud`, `vertex_type=InvestigationCase`, and `vertex_id=HHG-TEST-MEM`. The tool reported `deleted_count=1`.

## Runtime And Dependencies

- Python `3.11.15`; pip `24.0`
- `mcp==1.26.0`; `tigergraph-mcp==1.0.3`
- `langgraph==1.2.11`; `langchain-core==1.6.1`; `langchain` is not installed in this runtime
- `google-genai==2.9.0`; `pydantic==2.13.4`

## Live Graph Verification

Graph: `HHGOA_Fraud`

| Vertex type | Count |
| --- | ---: |
| Customer | 1,896 |
| Card | 1,926 |
| Transaction | 26,643 |
| DeviceProfile | 547 |
| ClosedCase | 5,565 |
| InvestigationCase | 20 |
| **Total** | **36,597** |

| Edge type | Count |
| --- | ---: |
| HAS_TRANSACTION | 26,643 |
| OWNS_CARD | 20 |
| MADE_WITH_CARD | 26,643 |
| HAS_IDENTITY | 4,270 |
| CUSTOMER_HAS_CASE | 5,565 |
| CASE_INCLUDES_TXN | 587 |
| CASE_ON_CARD | 5,565 |
| INVESTIGATION_FLAGS_TXN | 20 |
| INVESTIGATION_FOR_CUSTOMER | 20 |
| **Total** | **69,333** |

Read-only MCP verification confirmed `HHG-007 -> INVESTIGATION_FLAGS_TXN -> 3514948` and `HHG-007 -> INVESTIGATION_FOR_CUSTOMER -> C09933`. `get_transaction_context(3514948, 1)` returned owner `C09933`. The braces-only IDs `Transaction:{}`, `Card:{}`, and `ClosedCase:{}` are absent.

## GSQL Deployment

All five query sources below target `HHGOA_Fraud` and are installed, confirmed through the official MCP `tigergraph__is_query_installed` tool:

- `get_transaction_context`
- `get_customer_case_history`
- `detect_region_anomaly`
- `detect_shared_device`
- `detect_velocity_burst`

## MCP Production Transport

Production architecture is frozen as: `LangGraph -> AgentTools -> TigerGraphMCPClient -> ClientSession -> stdio_client -> tigergraph-mcp -> HHGOA_Fraud`.

The final read-only protocol check launched `python -m tigergraph_mcp.main --transport stdio`, completed `initialize`, `tools/list` (69 tools), and a representative installed-query `tools/call`. The production adapter uses discovered MCP tool names, records protocol traces, and exposes MCP failures without direct pyTigerGraph fallback. Static production-agent search found no operational direct database call; the only `pyTigerGraph` match is a boundary-description docstring.

## Policy And Evidence

`PolicyEngine`, `policy_rules.json`, `Evidence`, and `EvidenceLedger` are frozen. Existing tests cover citation validation, provenance, contradiction handling, bounded additional-evidence routing, MCP-unavailable behavior, and deterministic reasoning fallback. The official benchmark did not enter the additional-evidence branch: capability exists and is separately tested.

## Benchmark Snapshot

Official artifacts:

- `docs/PHASE3_EVALUATION_REPORT.md`
- `docs/PHASE3_EVALUATION_RESULTS.json`
- `docs/PHASE3_BENCHMARK_RUN.log`

Verified results: 20/20 completed, 120 total MCP tool calls consisting of 100 installed-query calls and 20 `tigergraph__add_nodes` writebacks, 0 MCP failures, 19 `confirmed_fraud`, 1 `cleared`, 100% citation validity, and 0 policy violations.

Outcome distribution is reported. Accuracy is not computed because `dataset/case_pack.csv` has no fraud ground-truth labels. `exposure_usd=0` in the output because the benchmark case input does not pass an amount field into the runner. Gemini returned quota (`429`) errors during the run; final `reasoning_source` is truthfully recorded as `deterministic_fallback` for all 20 cases.

## Test And Secret Hygiene

- Regression: `67 passed in 59.05s` using `pytest fraud_investigation/tests -q`.
- `.env` is ignored and not tracked. No credential pattern was found in tracked source or official benchmark artifacts. Secrets are not recorded here.
- `git diff --check` reports one pre-existing trailing blank line in `fraud_investigation/tests/test_ingestion.py`; it was not changed during this frozen checkpoint.

## SHA-256 Source Manifest

| Path | SHA-256 |
| --- | --- |
| `fraud_investigation/agent/mcp_client.py` | `049e1eca19899c09bba3c8ea82eacaedc404b36589053d266bb2f9c14bf01bf5` |
| `fraud_investigation/agent/tools.py` | `ffaea9790c7927e949f8ca3d64e88e094051e139a56253eaf362cc45df061261` |
| `fraud_investigation/agent/runner.py` | `337affd0d0cea6edded94597a432ea85d6fabadb98ac5ae63002ac928323cdad` |
| `fraud_investigation/agent/state.py` | `0af1c802a5d3e36edc407f99097fbacc8754920074b79e90159c01d5f044abdd` |
| `fraud_investigation/agent/nodes.py` | `c0d551e2471699e866fef59981feb9acdce7c1cd71df3f89bbf8fb9aaf70bf31` |
| `fraud_investigation/agent/graph.py` | `d671c53e38bd6ae82cd2b05382eaa4b440e1339de79368fc46983c2eff7c9533` |
| `fraud_investigation/policy/engine.py` | `95a240bb0508d4a51bfc47d4ee6f1b234859062d8a242d68635f262ca0c59e25` |
| `fraud_investigation/config/policy_rules.json` | `1fe2d960aedc472eae5cc44ee6ec0f3455b8c70dff9d69b45a214d7911d51929` |
| `fraud_investigation/evidence/ledger.py` | `c82afbe8f13c72115d0623f3ddd8e5180f4f7abe119d09bb80b10015480c2855` |
| `fraud_investigation/evidence/model.py` | `6a67d3d570458b06d8accdf8e6fdc7c7f58606773fddf20f27eaa85ad0f359d0` |
| `fraud_investigation/evaluation/runner.py` | `8c036bdf9bcf3bb04a637abe6d69e954497aeb15e2d1d66bd9cfadd60dd94706` |
| `fraud_investigation/evaluation/metrics.py` | `c95c647540e2fa8ca81c348853e44cf2471335536b228286ee184d3de6b96567` |
| `fraud_investigation/evaluation/report.py` | `69f752a8b730ecd499a8cda25f7255416567d5f20a4ec7505acb331a1df7661a` |
| `fraud_investigation/evaluation/run_eval.py` | `6e770f278db433c344809f5d41356fe9e50b249dcdfb1df269a9d484d6ba47df` |
| `fraud_investigation/queries/01_get_transaction_context.gsql` | `b3e42b4cf14e61f6a89684c3c1c94eecd8cccba46d7a085c0fff84fc6fd3380e` |
| `fraud_investigation/queries/02_get_customer_case_history.gsql` | `4cbfb67a05a0fb2929e4a927ec21421c91f803a3090639ffd780fb1a422e3d96` |
| `fraud_investigation/queries/03_detect_region_anomaly.gsql` | `14e43e9d3eb3ae2e8f5f4f4b3a066abb4919dfe0f8c3fcb7ac9245555d700665` |
| `fraud_investigation/queries/04_detect_shared_device.gsql` | `657ccd034077ca5a07505db30fac77755832a8c9f90a4dd1b185c302b78fd643` |
| `fraud_investigation/queries/05_detect_velocity_burst.gsql` | `696218da136d6064550c2c839a0695a02552dbf1326c2eca8aa689d0a99e3be5` |
