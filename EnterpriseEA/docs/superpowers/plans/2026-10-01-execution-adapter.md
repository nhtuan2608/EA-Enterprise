# Disabled-by-Default Execution Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real MT5 order/modify/cancel adapter that is disabled by default, fail-closed, demo-first, idempotent and reconciliation-driven, without implementing a Paper ledger or automatically sending orders. Define the later paperless controlled-live route without declaring live readiness.

**Architecture:** Keep strategy/observer modules separate from `Runtime/ExecutionAdapter.mqh`. Pure Python contracts model preflight/result/race semantics; MQL5 adapters call mutating APIs only behind an explicit disabled-by-default gate and persist intent/result audit. Every request is followed by authoritative active-state/history reconciliation.

**Tech Stack:** MQL5 strict mode, MetaEditor build 6230, Python 3.11 standard-library `unittest`, existing MT5 Files atomic writer/audit log.

**Spec:** `EnterpriseEA/docs/superpowers/specs/2026-10-01-execution-adapter-design.md`

## Global Constraints

- `InpExecutionEnabled=false` is the default and causes every execution request to be rejected before any MT5 trade API call.
- `InpObserverOnly=false` remains a startup refusal unless a separate future execution profile explicitly enables it; this increment does not enable that profile.
- No execution request is accepted without fresh account/positions/orders/deals reconciliation and a valid symbol specification.
- A unique correlation ID and idempotency key are mandatory; an already accepted key is rejected as duplicate without a second broker request.
- Request acknowledgements are not fill/cancel confirmation; fresh broker reconciliation is mandatory.
- Timeout, restart, missing history, callback race, identity change or stale snapshot yields `EXECUTION_UNKNOWN`, keeps entries blocked and never silently retries.
- Paper/virtual execution is permanently excluded; no Paper ledger is created, implied, or used as evidence.
- No automatic request from startup, timer, OnTick, symbol panel Refresh or transaction callback.
- No live enablement or go-live authorization in this increment.
- The paperless controlled-live route requires all gates in `docs/superpowers/specs/2026-10-01-paperless-controlled-live-design.md`: runtime compile, applicable demo/retained evidence, approved risk policy, manual authorization, tested kill switch, tested rollback, and durable audit.
- A missing or stale gate keeps status `NOT_AUTHORIZED`; compile, offline tests, or adapter presence do not establish live readiness.

---

### Task 1: Pure execution intent/result oracle (TDD)

**Files:**
- Create: `EnterpriseEA/Tests/Fixtures/execution-adapter-v0.1.0.json`
- Create: `EnterpriseEA/Tests/execution_adapter_oracle.py`
- Create: `EnterpriseEA/Tests/execution_adapter_tests.py`
- Create: `EnterpriseEA/Runtime/ExecutionContracts.mqh`

**Interfaces:**
- Produces Python `preflight(intent, context) -> dict`, `apply_result(state, result) -> dict`, `idempotency_decision(state, key) -> dict`.
- Produces MQL structs `EEA_ExecutionIntent`, `EEA_ExecutionResult`, `EEA_ExecutionGate`, defaults and pure validators.

- [ ] **Step 1: Write failing tests**

```python
def test_disabled_default_rejects_without_request():
    result = preflight(intent(), context(execution_enabled=False))
    assert result["confirmation_state"] == "NOT_SENT"
    assert result["reason_code"] == "EXECUTION_DISABLED"
    assert result["request_sent"] is False


def test_stale_reconciliation_blocks_preflight():
    result = preflight(intent(), context(execution_enabled=True, reconciliation_fresh=False))
    assert result["confirmation_state"] == "NOT_SENT"
    assert result["reason_code"] == "RECONCILIATION_STALE"


def test_duplicate_idempotency_key_never_sends_second_request():
    state = {"accepted_keys": ["idem-1"]}
    result = idempotency_decision(state, "idem-1")
    assert result == {"accepted": False, "reason_code": "DUPLICATE_IDEMPOTENCY_KEY"}


def test_acknowledgement_requires_reconciliation_confirmation():
    result = apply_result({}, {"request_sent": True, "request_retcode": "DONE", "broker_confirmed": False})
    assert result["confirmation_state"] == "EXECUTION_UNKNOWN"
```

- [ ] **Step 2: Run RED**

Run: `python -m unittest Tests/execution_adapter_tests.py -v`  
Expected: import failure because execution oracle/contracts do not exist.

- [ ] **Step 3: Implement Python oracle and pure MQL contracts**

Use exact reason codes `EXECUTION_DISABLED`, `RECONCILIATION_STALE`, `ACCOUNT_IDENTITY_MISMATCH`, `SYMBOL_SPEC_INVALID`, `DUPLICATE_IDEMPOTENCY_KEY`, `EXECUTION_UNKNOWN`, `REQUEST_ACCEPTED`, `CONFIRMED`, `REJECTED`. Keep all results entries-blocked unless fresh confirmation exists.

- [ ] **Step 4: Run targeted and full tests**

Run: `python -m unittest Tests/execution_adapter_tests.py -v`  
Run: `python -m unittest discover -s Tests -p '*tests.py' -v`  
Expected: targeted tests pass and pre-existing suite remains green.

- [ ] **Step 5: Commit**

```powershell
git add Tests/Fixtures/execution-adapter-v0.1.0.json Tests/execution_adapter_oracle.py Tests/execution_adapter_tests.py Runtime/ExecutionContracts.mqh
git commit -m "feat: add disabled execution contracts"
```

---

### Task 2: Disabled gate and audit/idempotency store (TDD)

**Files:**
- Modify: `EnterpriseEA/Tests/execution_adapter_tests.py`
- Modify: `EnterpriseEA/Storage/RuntimeEvidenceStore.mqh`
- Modify: `EnterpriseEA/Runtime/ExecutionContracts.mqh`
- Create: `EnterpriseEA/Runtime/ExecutionGate.mqh`

**Interfaces:**
- `bool EEA_ExecutionGateCheck(const EEA_ExecutionIntent&, const EEA_RuntimeAccountSnapshot&, const EEA_RuntimeReconciliationSnapshot&, const EEA_RuntimeSymbolSpec&, const bool execution_enabled, EEA_ExecutionResult&)`.
- `bool EEA_ExecutionStoreWriteIntent(...)` and `bool EEA_ExecutionStoreWriteResult(...)`, both atomic and redacted.

- [ ] **Step 1: Write failing tests**

Assert the gate rejects disabled/stale/identity-mismatch/spec-invalid/duplicate requests, stores idempotency marker before any future request, writes no raw login/name, and has no Paper ledger path.

- [ ] **Step 2: Run RED**

Run: `python -m unittest Tests/execution_adapter_tests.py -v`  
Expected: FAIL because gate/store interfaces are absent.

- [ ] **Step 3: Implement gate and atomic audit persistence**

The gate must check `execution_enabled`, observer mode, account fingerprint/server/config binding, `OBSERVING` reconciliation, age/window, symbol fingerprint, volume/price validity, nonempty correlation/idempotency, and duplicate key. Store files under `current/execution_intent.json`, `current/execution_result.json`, and `logs/execution_audit.jsonl`; no Paper ledger.

- [ ] **Step 4: Run GREEN and commit**

Run targeted/full suites and commit:

```powershell
git add Runtime/ExecutionContracts.mqh Runtime/ExecutionGate.mqh Storage/RuntimeEvidenceStore.mqh Tests/execution_adapter_tests.py
git commit -m "feat: add fail-closed execution gate"
```

---

### Task 3: Read-only post-request reconciliation bridge

**Files:**
- Modify: `EnterpriseEA/Runtime/ObserverRuntime.mqh`
- Modify: `EnterpriseEA/Tests/execution_adapter_tests.py`
- Create: `EnterpriseEA/Runtime/ExecutionReconciliation.mqh`

**Interfaces:**
- `bool EEA_ExecutionReconcileResult(EEA_ExecutionResult&, const EEA_RuntimeReconciliationSnapshot&, const long request_ticket, const string request_action)`.
- `EEA_ExecutionResult` transitions `REQUEST_ACCEPTED` to `CONFIRMED` only when active/history evidence proves it; otherwise `EXECUTION_UNKNOWN`.

- [ ] **Step 1: Write failing tests**

Cover market fill in deal/position history, pending order remaining active, confirmed cancel only after active order disappears and history proves terminal state, modify confirmation from active protective fields, timeout/missing evidence/race => unknown, and duplicate callback idempotency.

- [ ] **Step 2: Run RED**

Run focused execution tests and verify missing bridge functions fail.

- [ ] **Step 3: Implement pure read-only reconciliation bridge**

No trade API call. Use existing broker reconciliation rows and watermarks. Preserve entries blocked on unknown/race.

- [ ] **Step 4: Run GREEN and commit**

```powershell
git add Runtime/ExecutionReconciliation.mqh Runtime/ObserverRuntime.mqh Tests/execution_adapter_tests.py
git commit -m "feat: reconcile execution outcomes authoritatively"
```

---

### Task 4: MQL5 execution adapter, disabled by default

**Files:**
- Create: `EnterpriseEA/Runtime/ExecutionAdapter.mqh`
- Modify: `EnterpriseEA/EnterpriseEA.mq5`
- Modify: `EnterpriseEA/Tests/execution_adapter_tests.py`
- Modify: `EnterpriseEA/Runtime/ExecutionGate.mqh`

**Interfaces:**

```mql5
bool EEA_ExecutionPreflight(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
                            const bool execution_enabled,
                            EEA_ExecutionResult &result);

bool EEA_ExecutionSubmit(CAuditLog &audit,
                         const EEA_ExecutionIntent &intent,
                         EEA_ExecutionResult &result);

bool EEA_ExecutionModifyProtective(CAuditLog &audit,
                                    const EEA_ExecutionIntent &intent,
                                    EEA_ExecutionResult &result);

bool EEA_ExecutionCancelPending(CAuditLog &audit,
                                const EEA_ExecutionIntent &intent,
                                EEA_ExecutionResult &result);
```

- [ ] **Step 1: Add failing static-boundary tests**

Assert execution source includes the expected MT5 APIs only behind gate functions, no call site exists in `OnInit`, `OnTimer`, `OnTick`, `OnChartEvent`, or `OnTradeTransaction`, and default input is `false`.

- [ ] **Step 2: Run RED**

Run: `python -m unittest Tests/execution_adapter_tests.py -v`  
Expected: FAIL because adapter/input are absent.

- [ ] **Step 3: Implement adapter**

Use `MqlTradeRequest`/`OrderSend` for submit, `TRADE_ACTION_SLTP` with a position ticket for position protective changes, `TRADE_ACTION_MODIFY` with an order ticket for pending-order protective changes, and `TRADE_ACTION_REMOVE` for pending cancel. Every function immediately records request acknowledgement, never confirmation, and returns with `EXECUTION_UNKNOWN` until an external caller supplies fresh reconciliation. Never call these from EA lifecycle events.

- [ ] **Step 4: Compile and run tests**

Run full Python suite and MetaEditor build 6230. Require `0 errors, 0 warnings`. Static scan must confirm all APIs are confined to `Runtime/ExecutionAdapter.mqh` and no automatic call path exists.

- [ ] **Step 5: Commit**

```powershell
git add Runtime/ExecutionAdapter.mqh EnterpriseEA.mq5 Runtime/ExecutionGate.mqh Tests/execution_adapter_tests.py
git commit -m "feat: add disabled execution adapter"
```

---

### Task 5: Controlled demo activation protocol and documentation

**Files:**
- Modify: `EnterpriseEA/docs/superpowers/specs/2026-10-01-execution-adapter-design.md`
- Modify: `EnterpriseEA/docs/superpowers/plans/2026-10-01-execution-adapter.md`
- Modify: `EnterpriseEA/README.md`
- Modify: `EnterpriseEA/PHASE3_TRACEABILITY.md`
- Modify: `EnterpriseEA/PHASE4_TRACEABILITY.md`
- Create: `EnterpriseEA/docs/superpowers/specs/2026-10-01-paperless-controlled-live-design.md`
- Create: `EnterpriseEA/docs/superpowers/plans/2026-10-01-paperless-controlled-live.md`

- [ ] **Step 1: Add failing documentation/static-status tests**

Require exact labels `IMPLEMENTED_DISABLED_BY_DEFAULT`, `PAPER_EXCLUDED_PERMANENTLY`, `NOT_AUTHORIZED`, `EXECUTION_UNKNOWN`, and `RUNTIME_EVIDENCE_PENDING` in the report.

- [ ] **Step 2: Run RED**

Run execution tests and confirm report/status labels are absent.

- [ ] **Step 3: Write runbook**

Document preflight, demo-only activation, one controlled operation, confirmation/reconciliation, rollback/unknown handling, side-effect before/after snapshots, and explicit no-live/no-Paper boundaries. The paperless controlled-live documents must also list the seven mandatory gates and record evidence status without claiming readiness. Do not put secrets or raw account-holder identity in artifacts.

- [ ] **Step 4: Run final verification and commit**

Run full test suite, MetaEditor compile, static API scan, inspect clean Git status and commit:

Review only the allowed documentation files and verify that no code or test files changed. The final documentation must retain `NOT_AUTHORIZED` until the seven gates are evidenced.

## Final acceptance

- All offline tests pass.
- MetaEditor build 6230 reports `0 errors, 0 warnings`.
- Execution adapter exists but default is disabled and no lifecycle path calls it automatically.
- Every request has idempotency/correlation, fresh reconciliation, audit, redaction and unknown-state handling.
- Paper ledger is permanently excluded.
- No live operation is performed or authorized by this plan.
- Retained-terminal observer evidence remains separately classified as `RUNTIME_EVIDENCE_PENDING` until the applicable GUI/runtime protocol actually passes.
- Paperless controlled-live remains `NOT_AUTHORIZED` until runtime compile, applicable demo/retained evidence, risk policy, manual authorization, kill switch, rollback, and audit are all evidenced.
