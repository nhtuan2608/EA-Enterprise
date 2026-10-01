# Controlled Execution Demo Runbook: EnterpriseEA Execution Gate & Adapter

## 1. Overview
This runbook defines the operational protocol, safety controls, and governance constraints for the `EnterpriseEA` controlled execution architecture up to commit `39c4398`. It outlines the gating mechanisms that separate offline test observation from live execution, establishing strict fail-closed boundaries.

## 2. Component States & Authorization Matrix
- **Execution Adapter (`Runtime/ExecutionAdapter.mqh`):** `IMPLEMENTED_DISABLED_BY_DEFAULT`. All order placement, modification, and cancellation functions are fully implemented in MQL5 but strictly guarded by `EEA_ExecutionGateCheck` where `execution_enabled = false` by default. No execution path is invoked from EA lifecycle events (`OnInit`, `OnTick`, `OnTimer`, `OnChartEvent`, `OnTradeTransaction`).
- **Paper Ledger (`Storage/LedgerCheckpoint.mqh`, `Runtime/BrokerReconciliationAdapter.mqh`):** `PAPER_PENDING / NOT_IMPLEMENTED`. Paper trade simulation ledgers and automated forward testing hooks are pending full integration and validation.
- **Live Trading Authorization:** `NOT_AUTHORIZED`. Live production deployment, real-money execution, and unverified broker interactions are strictly prohibited.
- **Retained Runtime & Observer (`Runtime/ObserverRuntime.mqh`):** `OPERATIONAL_OFFLINE / RUNTIME_PENDING`. Read-only telemetry, multi-symbol selection persistence, revision tracking, and atomic persistence are verified in offline unit test suites and isolated tester runs; live terminal persistence and soak verification remain pending.

## 3. Safety Invariants & Governance
1. **Disabled by Default:** The execution adapter requires explicit parameter configuration (`InpExecutionEnabled = true`) AND passing all 7 governance checks in `EEA_ExecutionGateCheck` before any trade request can be transmitted.
2. **Zero Lifecycle Invocation:** EA lifecycle handlers (`OnTick`, `OnTimer`, etc.) contain zero calls to `EEA_ExecutionSubmit` or any mutating order API (`OrderSend`, `OrderSendAsync`, `CTrade`, `OrderDelete`, `PositionClose`, `PositionModify`).
3. **Fail-Closed Principle:** Any ambiguity, mismatch in material symbol specifications, missing ledger checkpoints, or zero-day reconciliation drift immediately halts execution eligibility and logs failure audits to `logs/execution_audit.jsonl`.
4. **No Live / Demo Operation:** No live or demo trading operations are conducted under this specification or commit scope.

## 4. Verification Protocol
1. **Static Analysis:** Scan codebase for prohibited execution API calls outside of `ExecutionAdapter.mqh` and audited documentation.
2. **Offline Unit Tests:** Run the complete unittest suite across all risk, checkpoint, pending order, and execution adapter modules:
   ```powershell
   python -m unittest discover -s EnterpriseEA/Tests -p '*tests.py' -v
   ```
3. **MQL Compilation Check:** Compile `EnterpriseEA.mq5` in MetaEditor build 6230 to verify zero compilation errors and zero warnings.
