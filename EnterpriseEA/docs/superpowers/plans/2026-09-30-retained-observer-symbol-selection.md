# Retained-Terminal Observer and Symbol Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement broker-aware multi-symbol discovery, multi-select symbol resolution, a chart checkbox selection panel, retained-terminal restart/checkpoint proof, monotonic refresh telemetry, coalesced transaction invalidation, and bounded-history parity verification.

**Architecture:** Extend pure registry discovery and Python oracles, add runtime telemetry and multi-symbol context, build a narrow MQL5 chart panel for selection, integrate atomic symbol selection persistence, and verify against a real connected terminal.

**Tech Stack:** MQL5 strict mode, MetaEditor build 6230, Python 3.11 `unittest`, JSON fixtures, MT5 Files sandbox.

**Spec:** `EnterpriseEA/docs/superpowers/specs/2026-09-30-retained-observer-symbol-selection-design.md`

## Global Constraints

- Observer-only: no `OrderSend`, `OrderSendAsync`, `CTrade`, order modification/deletion, position close, partial close, BE, or trailing operations.
- `InpObserverOnly=false` must refuse startup.
- Terminal/account trade permission never grants EA execution permission.
- `EEA_StateCanAllowEntry` remains false for every state.
- Missing, stale, conflicting, incomplete, or identity-mismatched evidence fails closed.
- Persist no raw account login, account-holder name, credentials, tokens, or provider secrets.
- Stored snapshots are not broker truth; startup always performs a fresh MT5 read.
- Writes use same-directory temporary replacement via `EEA_WriteAtomicText`.
- Telegram remains paused.
- Target compile/runtime environment is MetaTrader 5 build 6230 and VTMarkets-Demo.
- No Paper/Live readiness claim follows from this increment.

## File Structure

- `EnterpriseEA/Market/SymbolRegistry.mqh`: extend pure broker symbol discovery, normalization, versioned aliases, candidate ranking, and multi-symbol batch resolution.
- `EnterpriseEA/Runtime/RuntimeEvidence.mqh`: add runtime instance ID, monotonic refresh generation, selection revision, telemetry counters, and telemetry validation.
- `EnterpriseEA/Runtime/SymbolSpecAdapter.mqh`: adapter for broker symbol enumeration and batch specification reads.
- `EnterpriseEA/Runtime/BrokerReconciliationAdapter.mqh`: multi-symbol reconciliation snapshot collection.
- `EnterpriseEA/Runtime/ObserverRuntime.mqh`: coordinator supporting multi-symbol refresh, timer telemetry, and coalesced transaction invalidation.
- `EnterpriseEA/Storage/RuntimeEvidenceStore.mqh`: atomic symbol selection serialization and enhanced status check.
- `EnterpriseEA/Runtime/SymbolSelectionPanel.mqh`: narrow chart multi-select UI panel and apply handler.
- `EnterpriseEA/Tests/symbol_registry_oracle.py`: Python oracle for multi-symbol resolution and ranking.
- `EnterpriseEA/Tests/runtime_evidence_oracle.py`: Python oracle for multi-symbol runtime and telemetry validation.
- `EnterpriseEA/Tests/symbol_registry_tests.py`: unit tests for enhanced symbol discovery and batch resolution.
- `EnterpriseEA/Tests/runtime_evidence_tests.py`: unit tests for telemetry, deduplication, and single refresh completion.
- `EnterpriseEA/EnterpriseEA.mq5`: shell integration for canonical list, checkbox panel, and timer/transaction hooks.

---

### Task 1: Enhanced symbol discovery and multi-symbol resolution (TDD)

**Files:**
- Modify: `EnterpriseEA/Tests/Fixtures/symbol-resolution-v0.1.0.json`
- Modify: `EnterpriseEA/Tests/symbol_registry_oracle.py`
- Modify: `EnterpriseEA/Tests/symbol_registry_tests.py`
- Modify: `EnterpriseEA/Market/SymbolRegistry.mqh`

**Interfaces:**
- Consumes: canonical CSV list, available broker symbols list, alias table (`DXY -> USDX`).
- Produces: `EEA_ResolveSymbolsBatch`, `EEA_DiscoverBrokerSymbols`, `EEA_RankSymbolCandidate`.

- [ ] **Step 1: Add failing tests for batch symbol resolution and ranking**

```python
def test_batch_resolution_and_ranking(self):
    available = [
        {"name": "EURUSD", "tradeable": False, "conversion_only": False},
        {"name": "EURUSD-VIP", "tradeable": True, "conversion_only": False},
        {"name": "mEURUSD", "tradeable": True, "conversion_only": False},
        {"name": "XAUUSD.crp", "tradeable": False, "conversion_only": True},
        {"name": "XAUUSD-VIP", "tradeable": True, "conversion_only": False},
        {"name": "USDX.", "tradeable": True, "conversion_only": False},
    ]
    rows = resolve_batch(["EURUSD", "XAUUSD", "DXY"], available)
    self.assertEqual([row["canonical_symbol"] for row in rows], ["EURUSD", "XAUUSD", "DXY"])
    self.assertEqual(rows[0]["status"], "AMBIGUOUS")
    self.assertEqual(rows[1]["broker_symbol"], "XAUUSD-VIP")
    self.assertEqual(rows[2]["broker_symbol"], "USDX.")
    self.assertEqual(rows[2]["reason_code"], "UNIQUE_ALIAS_ROOT_MATCH")
```

- [ ] **Step 2: Run pytest/unittest to verify RED**

Run: `python -m unittest EnterpriseEA/Tests/symbol_registry_tests.py -v`
Expected: FAIL due to missing batch resolver functions.

- [ ] **Step 3: Implement minimal Python oracle changes**

Add candidate ranking, alias expansion (`DXY -> USDX`), and multi-symbol batch evaluation in `symbol_registry_oracle.py`.

- [ ] **Step 4: Implement MQL5 enhanced symbol registry**

Implement `EEA_DiscoverBrokerSymbols`, versioned aliases, ranking rules, and multi-symbol batch resolution in `SymbolRegistry.mqh`.

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python -m unittest EnterpriseEA/Tests/symbol_registry_tests.py -v`
Expected: PASS.

- [ ] **Step 6: Commit changes**

Record changed files in the implementation report (or git commit if in worktree).

---

### Task 2: Runtime telemetry, selection store, and audit deduplication (TDD)

**Files:**
- Modify: `EnterpriseEA/Tests/runtime_evidence_oracle.py`
- Modify: `EnterpriseEA/Tests/runtime_evidence_tests.py`
- Modify: `EnterpriseEA/Runtime/RuntimeEvidence.mqh`
- Modify: `EnterpriseEA/Storage/RuntimeEvidenceStore.mqh`

**Interfaces:**
- Consumes: Telemetry counters, selection revision, audit event records.
- Produces: `EEA_RuntimeTelemetryValidate`, `EEA_RuntimeStoreWriteSymbolSelection`, `EEA_RuntimeStoreCheckSymbolSelection`.

- [ ] **Step 1: Add failing telemetry and audit deduplication tests**

Add Python unit tests asserting duplicate audit records, generation gaps, or non-monotonic telemetry counters are rejected.

- [ ] **Step 2: Run test to verify RED**

Run: `python -m unittest EnterpriseEA/Tests/runtime_evidence_tests.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement minimal MQL5/Python telemetry and store extensions**

Add instance ID, refresh generation, telemetry fields, and atomic symbol selection serialization (`symbol_selection.json`).

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python -m unittest EnterpriseEA/Tests/runtime_evidence_tests.py -v`
Expected: PASS.

- [ ] **Step 5: Commit changes**

---

### Task 3: Chart checkbox panel and shell integration

**Files:**
- Create: `EnterpriseEA/Runtime/SymbolSelectionPanel.mqh`
- Modify: `EnterpriseEA/Runtime/ObserverRuntime.mqh`
- Modify: `EnterpriseEA/EnterpriseEA.mq5`
- Modify: `EnterpriseEA/Tests/runtime_evidence_tests.py`

**Interfaces:**
- Consumes: Chart events (`CHARTEVENT_CLICK`), symbol discovery results, selection Apply action.
- Produces: UI multi-select checkbox matrix, atomic selection commit, updated observer runtime context.

- [ ] **Step 1: Add failing static and integration checks**

Assert chart panel source exists, contains no trade execution tokens, and integrates with `ObserverRuntime.mqh` and `EnterpriseEA.mq5`.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m unittest EnterpriseEA/Tests/runtime_evidence_tests.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement SymbolSelectionPanel.mqh and update ObserverRuntime.mqh**

Build narrow chart UI controls (checkboxes, status labels, Refresh, Apply) and connect selection revision increments to fresh reconciliation.

- [ ] **Step 4: Update EnterpriseEA.mq5**

Remove `InpBrokerSymbols`, add `InpCanonicalSymbols` and `InpShowSymbolPanel`, route `OnChartEvent` to the panel handler, and initialize multi-symbol coordinator.

- [ ] **Step 5: Run all unit tests**

Run: `python -m unittest discover -s EnterpriseEA/Tests -p '*tests.py' -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit changes**

---

### Task 4: Compile, deploy, and retained-terminal verification

**Files:**
- Create: `EnterpriseEA/artifacts/retained-terminal-runbook.md`
- Create: `EnterpriseEA/artifacts/retained-terminal-verification.md`
- Modify: implementation report and traceability docs.

**Interfaces:**
- Consumes: MetaEditor build 6230, connected MT5 terminal.
- Produces: build log, retained checkpoint files, soak telemetry records, before/after account state comparison.

- [ ] **Step 1: Compile with MetaEditor build 6230**

Compile `EnterpriseEA.mq5` and verify `0 errors, 0 warnings`.

- [ ] **Step 2: Deploy and verify retained terminal checkpoint & restart**

Attach EA in observer mode, verify checkpoint survival across terminal restart, and verify fresh reconciliation after compatible checkpoint.

- [ ] **Step 3: Run timer soak and audit verification**

Run 60-minute soak test, inspect audit JSONL for single-completion / zero-backlog invariants, and perform independent bounded history parity check.

- [ ] **Step 4: Final verification and traceability update**

Run full offline test suite and update traceability markdown files.
