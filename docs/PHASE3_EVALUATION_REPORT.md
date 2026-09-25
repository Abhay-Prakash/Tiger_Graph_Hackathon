# Phase 3 — Benchmark Evaluation & System Audit Report

## EXECUTIVE SUMMARY

- **Cases Evaluated:** 20
- **Completed Cases:** 20
- **Failed Cases:** 0
- **Ground Truth Available:** NO (Strictly distinguished from dataset pattern alignment per Section 5)

---

## 1. EVIDENCE GROUNDING

- **Total Evidence Objects Gathered:** 139
- **Valid Evidence Citations:** 139
- **Invalid / Hallucinated Citations:** 0
- **Citation Validity Rate:** 100.00%
- **Unsupported Claims:** 0

---

## 2. POLICY SAFETY INVARIANTS

- **Forbidden Action Leakage:** 0 (Target: 0)
- **Mandatory Action Omissions:** 0 (Target: 0)
- **Total Policy Violations:** 0 (Target: 0)
- **Policy Engine Version:** `hackathon-inferred-v1` (Deterministic Authority)

---

## 3. MCP BOUNDARY INTEGRITY

- **Total MCP Tool Calls Executed:** 120
- **GSQL Graph Query Calls:** 100
- **MCP Transport Failures:** 0
- **Direct pyTigerGraph Bypasses:** 0 (Strict Target: 0)

---

## 4. AGENTICITY & WORKFLOW DYNAMICS

- **Cases Requiring Additional Evidence:** 0
- **Additional Evidence Invocation Rate:** 0.00%
- **Maximum Observed Loop Depth:** 0 (Bounded at max 1)
- **NBA-Before Capture Rate:** 100.00%
- **NBA-After Capture Rate:** 100.00%

---

## 5. LLM REASONING & FALLBACK TRACING

- **Live LLM Reasoning Cases:** 0
- **Deterministic Fallback Cases:** 20
- **Live LLM Usage Rate:** 0.00%
- **Fallback Usage Rate:** 100.00%

---

## 6. PERFORMANCE TELEMETRY

- **Average Duration:** 25.4832 seconds
- **Median Duration:** 21.7098 seconds
- **Minimum Duration:** 19.9803 seconds
- **Maximum Duration:** 99.6144 seconds

---

## 7. HHG-007 REGRESSION AUDIT

- **Flagged Region vs Home Region Match:** `264.0 == 264.0` (`is_anomalous = false`)
- **`out_of_region_use` Asserted:** NOT ASSERTED
- **Regression Status:** PASS

---

## 8. Accuracy And Error Analysis

- No per-case ground-truth outcomes are present in `dataset/case_pack.csv`; a classification accuracy score is therefore not calculated.
- Execution errors: 0.
- MCP transport failure events: 0 across 0 cases.
- Cases using deterministic reasoning fallback: 20.
- Policy violations observed: 0.

---

## 9. NBA Before/After Matrix

| Case ID | NBA Before | Additional Evidence Requested | NBA After |
| :--- | :--- | :--- | :--- |
| `HHG-001` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-002` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-003` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-004` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-005` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-006` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-007` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-008` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-009` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-010` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-011` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-012` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-013` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-014` | CREATE_CASE, VERIFY_WITH_CUSTOMER, CLOSE_NO_FRAUD | none | none |
| `HHG-015` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-016` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-017` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-018` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-019` | CREATE_CASE, BLOCK_CARD | none | none |
| `HHG-020` | CREATE_CASE, BLOCK_CARD | none | none |

---

## 10. Additional Evidence And Contradictions

- Cases requiring additional evidence: none.
- Cases with contradiction evidence: HHG-002, HHG-004, HHG-005, HHG-006, HHG-007, HHG-008, HHG-009, HHG-010, HHG-011, HHG-013, HHG-014, HHG-016, HHG-020.
- Observed MCP writebacks through `tigergraph__add_nodes`: 20/20.

---

## 11. Per-Case Results

### HHG-001

- Trigger: `risk_score`; initial risk: `0.61`; transaction: `3514030`.
- Evidence: 7 items; citations: EVD-C98D47CE5297, EVD-F87F2564AAEB, EVD-E08A8058FE42, EVD-D5359B524548, EVD-5CC5D1B27062, EVD-E2151C84C69E, EVD-A393F0D763D6; sufficient: `True`.
- Hypotheses: out_of_region_use; confidence: `0.85`; uncertainty: `0.2`.
- Outcome/pattern/exposure: `confirmed_fraud` / `out_of_region_use` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-002

- Trigger: `risk_score`; initial risk: `0.79`; transaction: `3478782`.
- Evidence: 6 items; citations: EVD-F570121F4D55, EVD-D5B1BF444212, EVD-B9B6A9DA79CF, EVD-45938C9E74AE, EVD-7ACF3FEDC7D5, EVD-EF27206AC83C; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-003

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3530164`.
- Evidence: 7 items; citations: EVD-BE7BF4687388, EVD-B2A3DA9716AE, EVD-CC819C2413B7, EVD-F26B45BD33A7, EVD-287A33048AEB, EVD-DB13B1360E18, EVD-1737B1533300; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-004

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3583227`.
- Evidence: 7 items; citations: EVD-CFA552E300EF, EVD-41D51537A8A6, EVD-52CFAA9A6FE4, EVD-8ED974A03842, EVD-52944560E403, EVD-13257AE2AFC3, EVD-2542024A37BB; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-005

- Trigger: `risk_score`; initial risk: `0.54`; transaction: `3523199`.
- Evidence: 7 items; citations: EVD-89E630DDC448, EVD-D866F113BA5B, EVD-44F444829736, EVD-D75DF0FB4F46, EVD-85F3977DA287, EVD-C1FA80C17474, EVD-7DC93CC45B0F; sufficient: `True`.
- Hypotheses: account_takeover; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `account_takeover` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-006

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3476682`.
- Evidence: 7 items; citations: EVD-59421BC38F61, EVD-001437CD8318, EVD-BC69663BB25C, EVD-A229A22EF63F, EVD-DC94CE1081EC, EVD-BFD27538AC04, EVD-D36CA9B917EE; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-007

- Trigger: `risk_score`; initial risk: `0.87`; transaction: `3514948`.
- Evidence: 7 items; citations: EVD-75D480F6F6FF, EVD-B8E1AFF73FF9, EVD-A914DE513553, EVD-96428F33B5A6, EVD-9E5952F2D283, EVD-A1554D7D59D7, EVD-2AB526F45532; sufficient: `True`.
- Hypotheses: card_testing, account_takeover; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_testing` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-008

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3558054`.
- Evidence: 7 items; citations: EVD-91C048874EFF, EVD-A583E4F1605E, EVD-5F6793675374, EVD-2921E03ED8B5, EVD-FB9922BAFDE3, EVD-2BEEB517CEA6, EVD-41F82AAB3AAC; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-009

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3581141`.
- Evidence: 7 items; citations: EVD-51BB9C9522AD, EVD-AB378A558EBC, EVD-D29E3461C468, EVD-FB8E2BA856FE, EVD-5FB0A0FA8476, EVD-BD287D891EDD, EVD-5D17B68FAB3F; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-010

- Trigger: `risk_score`; initial risk: `0.9`; transaction: `3506725`.
- Evidence: 7 items; citations: EVD-9A79CDFA6193, EVD-9E9A5E1E7B31, EVD-A4131A2E14D0, EVD-76FD5477D13F, EVD-2DA283D33477, EVD-F240E7E9B51A, EVD-C550960A35D1; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-011

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3583368`.
- Evidence: 7 items; citations: EVD-849AE98C1597, EVD-4245A97DF38C, EVD-163AE28F5895, EVD-8DAA62FE0487, EVD-5EEDEAF17502, EVD-77741B51E0C2, EVD-6C1563985830; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-012

- Trigger: `risk_score`; initial risk: `0.55`; transaction: `3553342`.
- Evidence: 7 items; citations: EVD-56A01E6AC9BF, EVD-3B36B6B0D486, EVD-BA656801D366, EVD-69F03C760381, EVD-168881DEFCFE, EVD-225A7AAFA2B0, EVD-5FDFA263282C; sufficient: `True`.
- Hypotheses: out_of_region_use, card_testing; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `out_of_region_use` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-013

- Trigger: `risk_score`; initial risk: `0.76`; transaction: `3526826`.
- Evidence: 7 items; citations: EVD-566F882BF2F9, EVD-2BBB3BBB4520, EVD-E055F42D8C06, EVD-E59573E40E9D, EVD-6FD0A5778152, EVD-F851D6FA7106, EVD-18901905ACBB; sufficient: `True`.
- Hypotheses: card_testing, account_takeover; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_testing` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-014

- Trigger: `analyst_request`; initial risk: `0.0`; transaction: `3478561`.
- Evidence: 7 items; citations: EVD-090E6D8FA75E, EVD-C96F1CB0BE0A, EVD-D9F8280837E3, EVD-0F9545C1C6DD, EVD-6028C4B1B5A1, EVD-4EFF1E64F20F, EVD-7F6857A1ACC3; sufficient: `True`.
- Hypotheses: none; confidence: `0.8`; uncertainty: `0.2`.
- Outcome/pattern/exposure: `cleared` / `none` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, VERIFY_WITH_CUSTOMER, CLOSE_NO_FRAUD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-015

- Trigger: `risk_score`; initial risk: `0.77`; transaction: `3464869`.
- Evidence: 7 items; citations: EVD-9F2072513C8F, EVD-C3CF45111098, EVD-E9F9D3A7C376, EVD-E51D714883E7, EVD-E904B5C5A879, EVD-1EFE8F7B5979, EVD-C76E93C19D10; sufficient: `True`.
- Hypotheses: out_of_region_use, card_testing; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `out_of_region_use` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-016

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3534820`.
- Evidence: 7 items; citations: EVD-F6D4A0556746, EVD-625B0FC18DE7, EVD-0CF9D9701F78, EVD-A634C1612BB1, EVD-AFAC01469A07, EVD-A96F3B8312A3, EVD-A76D2528C172; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-017

- Trigger: `risk_score`; initial risk: `0.57`; transaction: `3450629`.
- Evidence: 7 items; citations: EVD-3AD086A0B992, EVD-AB3793F98D7C, EVD-0FE62BBEA907, EVD-5B2CCF2463E5, EVD-84481F5FC2AD, EVD-9A700AE9356F, EVD-302D3E7C8FDC; sufficient: `True`.
- Hypotheses: out_of_region_use, card_testing; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `out_of_region_use` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-018

- Trigger: `customer_report`; initial risk: `0.0`; transaction: `3491361`.
- Evidence: 7 items; citations: EVD-97888CA36007, EVD-B64D0A70C26D, EVD-A230988D3BD8, EVD-244AC02E507E, EVD-D9DC27B91199, EVD-228E56B01614, EVD-C9EDE31433BD; sufficient: `True`.
- Hypotheses: card_not_present_fraud; confidence: `0.9`; uncertainty: `0.1`.
- Outcome/pattern/exposure: `confirmed_fraud` / `card_not_present_fraud` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-019

- Trigger: `risk_score`; initial risk: `0.9`; transaction: `3503878`.
- Evidence: 7 items; citations: EVD-8E43449D6A16, EVD-AB951F75F43E, EVD-13FE8CEF1991, EVD-C78F474E67B2, EVD-04DBC0193491, EVD-777BDAE8E1A6, EVD-F4ED457C1546; sufficient: `True`.
- Hypotheses: out_of_region_use; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `out_of_region_use` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.

### HHG-020

- Trigger: `risk_score`; initial risk: `0.52`; transaction: `3509359`.
- Evidence: 7 items; citations: EVD-03C4FEA7BEF7, EVD-ADF11E1DA03E, EVD-FAC578B74B5D, EVD-A00FE1ADA1F3, EVD-F0916F0292ED, EVD-482F79380CA2, EVD-945EE25A8860; sufficient: `True`.
- Hypotheses: account_takeover; confidence: `0.85`; uncertainty: `0.15`.
- Outcome/pattern/exposure: `confirmed_fraud` / `account_takeover` / `$0.00`.
- SAR required: `False`; executed actions: CREATE_CASE, BLOCK_CARD.
- Reasoning: `deterministic_fallback`; MCP transport: `stdio_mcp`; writeback observed: `True`.
- MCP failures: []; error: none.
