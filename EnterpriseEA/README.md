# EnterpriseEA offline foundation and prototypes

For development on a machine without MT5 or MetaEditor, follow [OFFLINE_WORKFLOW.md](OFFLINE_WORKFLOW.md). It separates offline contract evidence from the later MQL5 compile and runtime gates.

The [Phase 3 traceability table](PHASE3_TRACEABILITY.md) maps the offline modules to the specification and lists the broker/runtime evidence still required.

The [Phase 4 traceability table](PHASE4_TRACEABILITY.md) records the first closed-bar expected-path observation prototype and the execution work still required. Virtual execution is not a fallback: the Paper ledger is permanently excluded.

The [paperless controlled-live design](docs/superpowers/specs/2026-10-01-paperless-controlled-live-design.md) and [plan](docs/superpowers/plans/2026-10-01-paperless-controlled-live.md) define the only future controlled-live route. Runtime compile, applicable demo/retained evidence, approved risk policy, manual authorization, kill switch, rollback, and audit are mandatory gates. Until each gate has retained evidence, paperless controlled-live and live trading remain `NOT_AUTHORIZED`.

Master specification v1.4 (`Dac_ta_tong_the_EA_MT5_MCP_AI_News_Dashboard_v1_4.docx` at the repository root) removes the Paper route from every phase and checklist and adds the normative [appendix D](docs/spec-v1.4/APPENDIX_D_PAPERLESS.md): `PAPER_EXCLUDED_PERMANENTLY`, the seven controlled-live gates, the phase order without Paper, open decisions O-16 to O-18 and the 03/10/2026 progress snapshot. Rebuild it from v1.3 with `EnterpriseEA/Tests/update_spec_v1_4_docx.ps1` and the files in `docs/spec-v1.4/`.

The [control center UI design](docs/superpowers/specs/2026-10-03-control-center-ui-design.md) describes the separate Dashboard and Settings views, their spec 9.1 tabs, and the one-click interaction rules.

The [controlled-live activation runbook](artifacts/controlled-live-activation-runbook.md) describes the evidence sequence and the intentionally blocked authorization template.

The [setup-bound pending-order specification](PENDING_ORDER_LIFECYCLE_SPEC.md) and [implementation plan](PENDING_ORDER_LIFECYCLE_PLAN.md) add expiry, early cancellation, partial-fill remainder and broker reconciliation requirements for LIMIT/STOP orders. An isolated offline lifecycle prototype exists; no pending-order execution is connected to the EA shell.

The proposed [Telegram control specification](TELEGRAM_CONTROL_SPEC.md) covers remote status, AI questions and replies, and authenticated pause/resume of new entries. The offline command-gate prototype and JSON contracts are isolated; no Telegram gateway, AI reply delivery, or remote command execution has been connected to the EA shell.

This source tree contains versioned core contracts, a live-terminal-only observer panel, closed-bar S02 candidate scanning (disabled by default), and the paperless controlled-live orchestration. The shell includes read-only runtime evidence, current quote/cost/margin checks, structural levels, account-wide stress exposure, policy headroom, portfolio budget, volume sizing, strict risk release, durable intent/decision records, identity-bound authorization, controller scope, market submission, and reconciliation. `InpObserverOnly=true`, `InpExecutionEnabled=false`, and `InpLiveTradeArmed=false` remain the defaults; missing gates fail closed. The adapter is offline-tested and MetaEditor-compiled; no compile or bounded tester result is live authorization.

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
- `Runtime/`: account, symbol, reconciliation, quote, authorization, controller and execution boundaries. `Runtime/ExecutionAdapter.mqh` remains `IMPLEMENTED_DISABLED_BY_DEFAULT`; the controlled-live scope is market-only (BUY/SELL), with pending-order operations hard-denied. `Integration/ControlledLiveRuntime.mqh` is the opt-in risk-to-submit route. Paper execution is `PAPER_EXCLUDED_PERMANENTLY`; there is no Paper ledger or Paper parity path. Live execution and paperless controlled-live remain `NOT_AUTHORIZED` until the documented mandatory gates have retained evidence.
- `Integration/ControlledLiveRuntime.mqh`: paperless candidate-to-risk-release-to-market-intent orchestration; it requires explicit live inputs, exact identity-bound authorization, durable controller scope, fresh evidence, and persists the risk decision before submit.
- `Storage/LiveAuthorizationStore.mqh` and `Storage/RiskDecisionStore.mqh`: redacted authorization/risk-release persistence with identity and expiry checks.
- `Storage/RuntimeEvidenceStore.mqh`: deterministic account/symbol/reconciliation/status JSON writer using the existing atomic replacement helper.

Runtime files are written under the terminal's `MQL5/Files/EnterpriseEA/` sandbox. Audit JSONL is UTF-8 without a BOM. Each append is flushed; on startup an incomplete final line is copied out and the same-directory temp file replaces the log, keeping only complete lines. Readers should still reject malformed complete lines and report them. The EA writes startup/shutdown audit events to `logs/audit.jsonl`. JSON config is a contract fixture for this phase; external config loading and schema validation in MQL5 are not implemented.

`current/shared_state.json` is a deliberately narrow boot checkpoint for this Phase 1 slice. It stores only schema/config versions and the known empty/unselected state. At startup the EA checks those markers and status values; it does not deserialize positions, active policies, symbol metadata, or account figures. A missing file is initialized; an incompatible file is preserved, audited, and forces blocked/unknown state. This is not a restart/reconcile implementation for later trading state.

The ledger checkpoint prototype is separate from `current/shared_state.json` and is not yet written or read by the EA shell. It defines validation and fail-closed restoration of historical aggregates only. No file serializer/parser, per-position lineage restoration, broker replay, or crash recovery has been proven.

## Contract checks

From the workspace root run:

```powershell
python -m unittest discover -s EnterpriseEA/Tests -p '*tests.py' -v
```

These checks validate JSON syntax, core required fields, fail-closed defaults, FTMO floor/headroom fixtures, runtime evidence contracts/adapters, account financial snapshots, trade quote boundaries, risk-release lineage, live-authorization identity binding, controller defaults, controlled-live orchestration and static execution/storage boundaries. The current suite contains 301 tests. The exact-target MetaEditor source compile records 0 errors and 0 warnings; tools/compile_target.ps1 -RequireBinaryChanged must also confirm that the target EX5 actually changed before deployment is considered complete. No demo or live operation was performed; retained-sandbox checkpoint restart proof, target execution scenarios, and live authorization remain pending. These results do not authorize live trading, and there is no Paper validation requirement because the Paper ledger is permanently excluded.

## Phase boundaries

The observer profile keeps entry permission blocked. The explicitly armed live profile has a real market-only route, but remains unavailable unless every mandatory gate is evidenced and manually authorized. Pending-order and broader trade-management operations remain separate work. The only execution route is paperless and must pass every mandatory gate; no live readiness is claimed from offline, demo, or bounded tester evidence alone. `FTMO_1_STEP` and `FTMO_2_STEP` schema constraints reflect the v1.1 specification; live risk inputs are operator-bound and must be evidenced for the exact account/window.
