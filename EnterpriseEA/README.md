# EnterpriseEA offline foundation and prototypes

For development on a machine without MT5 or MetaEditor, follow [OFFLINE_WORKFLOW.md](OFFLINE_WORKFLOW.md). It separates offline contract evidence from the later MQL5 compile and runtime gates.

The [Phase 3 traceability table](PHASE3_TRACEABILITY.md) maps the offline modules to the specification and lists the broker/runtime evidence still required.

The [Phase 4 traceability table](PHASE4_TRACEABILITY.md) records the first closed-bar expected-path observation prototype and the virtual order/fill work still required.

The [setup-bound pending-order specification](PENDING_ORDER_LIFECYCLE_SPEC.md) and [implementation plan](PENDING_ORDER_LIFECYCLE_PLAN.md) add expiry, early cancellation, partial-fill remainder and broker reconciliation requirements for LIMIT/STOP orders. An isolated offline lifecycle prototype exists; no pending-order execution is connected to the EA shell.

The proposed [Telegram control specification](TELEGRAM_CONTROL_SPEC.md) covers remote status, AI questions and replies, and authenticated pause/resume of new entries. The offline command-gate prototype and JSON contracts are isolated; no Telegram gateway, AI reply delivery, or remote command execution has been connected to the EA shell.

This source tree contains versioned core contracts, an observer-only MQL5 shell, and isolated Phase 2/3/4 calculation prototypes. The shell now includes a read-only runtime evidence adapter for explicit symbol specifications and bounded account positions/orders/deals snapshots; it still does not scan setup market data, size positions, grant entry permission, render a dashboard, invoke AI/news services, or place/modify/cancel orders. The adapter is offline-tested, MetaEditor-compiled, and has produced versioned evidence in an isolated MT5 tester run. That evidence is bounded to the declared tester history window and is not full account lineage or Paper approval.

## Contents

- `Core/`: config defaults/validation, typed shared state and event envelope.
- `Storage/`: same-directory temp-file replacement helper and flushed JSONL audit writer.
- `schemas/`: versioned config, shared state, symbol registry, account policy, snapshots and event contracts.
- `config/observer-v1.0.0.json`: explicit unselected policy and empty symbol registry; no broker/account assumptions.
- `Tests/`: stdlib-only contract checks and clearly labeled specification fixtures.
- `Setups/BreakRetest.mqh`: isolated Phase 2 S02 closed-bar prototype; see [S02_OFFLINE.md](Setups/S02_OFFLINE.md). It is not included by the EA shell.
- `Risk/StructuralLevels.mqh`: isolated Phase 3 price geometry proposal; see [STRUCTURAL_OFFLINE.md](Risk/STRUCTURAL_OFFLINE.md). It does not grant entry permission.
- `Risk/FtmoHeadroom.mqh`: isolated Phase 3 FTMO 1-Step/2-Step policy-floor headroom calculation; see [FTMO_HEADROOM_OFFLINE.md](Risk/FTMO_HEADROOM_OFFLINE.md). It is not entry permission and is not wired into the shell.
- `Risk/DailyResetLedger.mqh`: isolated reset-snapshot sequence and 1-Step high-water calculation; see [DAILY_RESET_LEDGER_OFFLINE.md](Risk/DAILY_RESET_LEDGER_OFFLINE.md). Prague midnight must be attested upstream.
- `Risk/AccountRiskLedger.mqh`: isolated reducer for caller-reconciled account-wide snapshots; see [ACCOUNT_RISK_LEDGER_OFFLINE.md](Risk/ACCOUNT_RISK_LEDGER_OFFLINE.md). It does not read broker history itself.
- `Risk/PortfolioBudget.mqh`: isolated account-wide pre-sizing budget calculation; see [PORTFOLIO_BUDGET_OFFLINE.md](Risk/PORTFOLIO_BUDGET_OFFLINE.md). Reconciliation and portfolio limits are caller inputs.
- `Risk/VolumeSizing.mqh`: isolated Phase 3 volume sizing from validated loss-per-lot and margin quotes; see [VOLUME_SIZING_OFFLINE.md](Risk/VOLUME_SIZING_OFFLINE.md). It is not wired into the shell.
- `Risk/TradeEconomics.mqh`: isolated Phase 3 net reward/risk check; see [TRADE_ECONOMICS_OFFLINE.md](Risk/TRADE_ECONOMICS_OFFLINE.md). It is not entry permission.
- `Market/SymbolRegistry.mqh`: explicit canonical-to-broker symbol resolution; see [SYMBOL_REGISTRY_OFFLINE.md](Market/SYMBOL_REGISTRY_OFFLINE.md). Prefix/suffix matches are advisory only.
- `Integration/DryRunCandidateGate.mqh`: isolated composition of the Phase 2/3 results; see [DRY_RUN_CANDIDATE_GATE_OFFLINE.md](Integration/DRY_RUN_CANDIDATE_GATE_OFFLINE.md). Its positive result is review only.
- `Storage/LedgerCheckpoint.mqh`: isolated versioned restore contract for daily reset history and account-risk aggregates; see [LEDGER_CHECKPOINT_OFFLINE.md](Storage/LEDGER_CHECKPOINT_OFFLINE.md). Restore blocks new entries pending current-day reset attestation and fresh broker reconciliation.
- `Integration/RemoteModeGate.mqh`: isolated Telegram command proposal gate for pause and two-step resume; see [REMOTE_MODE_GATE_OFFLINE.md](Integration/REMOTE_MODE_GATE_OFFLINE.md). A positive result still requires durable commit and EA/runtime safety checks.
- `TradeManager/ExpectedPath.mqh`: isolated Phase 4 closed-bar path observer after an attested virtual fill; see [EXPECTED_PATH_OFFLINE.md](TradeManager/EXPECTED_PATH_OFFLINE.md). It records MFE/MAE and review reasons but never changes an order or position.
- `TradeManager/PendingOrderLifecycle.mqh`: isolated Phase 4 pending-order state machine for caller-attested LIMIT/STOP events; see [PENDING_ORDER_LIFECYCLE_OFFLINE.md](TradeManager/PENDING_ORDER_LIFECYCLE_OFFLINE.md). It cannot submit or cancel real orders.
- `Storage/PendingOrderCheckpoint.mqh`: isolated v1.1 checkpoint restore contract for pending orders and audit-tail binding; see [PENDING_ORDER_CHECKPOINT_OFFLINE.md](Storage/PENDING_ORDER_CHECKPOINT_OFFLINE.md). It preserves exposure and blocks entries pending fresh broker reconciliation, with no file or broker I/O.
- `Storage/PendingOrderAudit.mqh`: isolated transition audit and fingerprint-chain contract; see [PENDING_ORDER_AUDIT_OFFLINE.md](Storage/PENDING_ORDER_AUDIT_OFFLINE.md). It checks order identity, sequence and volume/risk changes but does not persist records or reconcile broker history.
- `schemas/remote-command.schema.json`, `schemas/telegram-ai-request.schema.json`, `schemas/telegram-ai-reply.schema.json`: versioned internal command and read-only AI question/reply contracts, backed by synthetic fixtures.
- `Runtime/`: observer-only MT5 account, explicit symbol-spec, and bounded broker reconciliation adapters plus coordinator. They are read-only, atomically persist runtime evidence, and never grant entry permission. `Runtime/ExecutionAdapter.mqh` provides order capabilities but is `IMPLEMENTED_DISABLED_BY_DEFAULT`. Offline tests and a clean MetaEditor build exist. See controlled execution demo documents: [artifacts/execution-demo-runbook.md](artifacts/execution-demo-runbook.md) and [artifacts/execution-demo-verification.md](artifacts/execution-demo-verification.md). Paper ledger is `PAPER_PENDING / NOT_IMPLEMENTED`, live execution is strictly `NOT_AUTHORIZED`, and no live/demo operations are active. Retained runtime integration remains pending.
- `Storage/RuntimeEvidenceStore.mqh`: deterministic account/symbol/reconciliation/status JSON writer using the existing atomic replacement helper.

Runtime files are written under the terminal's `MQL5/Files/EnterpriseEA/` sandbox. Audit JSONL is UTF-8 without a BOM. Each append is flushed; on startup an incomplete final line is copied out and the same-directory temp file replaces the log, keeping only complete lines. Readers should still reject malformed complete lines and report them. The EA writes startup/shutdown audit events to `logs/audit.jsonl`. JSON config is a contract fixture for this phase; external config loading and schema validation in MQL5 are not implemented.

`current/shared_state.json` is a deliberately narrow boot checkpoint for this Phase 1 slice. It stores only schema/config versions and the known empty/unselected state. At startup the EA checks those markers and status values; it does not deserialize positions, active policies, symbol metadata, or account figures. A missing file is initialized; an incompatible file is preserved, audited, and forces blocked/unknown state. This is not a restart/reconcile implementation for later trading state.

The ledger checkpoint prototype is separate from `current/shared_state.json` and is not yet written or read by the EA shell. It defines validation and fail-closed restoration of historical aggregates only. No file serializer/parser, per-position lineage restoration, broker replay, or crash recovery has been proven.

## Contract checks

From the workspace root run:

```powershell
python -m unittest discover -s EnterpriseEA/Tests -p '*tests.py' -v
```

These checks validate JSON syntax, core required fields, fail-closed defaults, FTMO floor/headroom fixtures, runtime evidence contracts/adapters, and static execution/storage boundaries. The current suite contains 144 tests. MetaEditor build 6230 compiles the integrated observer EA with 0 errors and 0 warnings. An isolated tester run produces account/symbol/reconciliation/status/audit artifacts and a second fresh-start run succeeds; retained-sandbox checkpoint restart proof and Paper validation remain pending.

## Phase boundaries

Entry permission always returns false in this phase. Observer scanning begins in Phase 2. Account policy selection, instrument resolution, runtime config loading, risk computation, account-wide reconciliation and dry-run execution remain later work. `FTMO_1_STEP` and `FTMO_2_STEP` schema constraints reflect the v1.1 specification; sample arithmetic values are test fixtures only.
