# MT5 Runtime Evidence Adapter Design

**Status:** Approved in-chat design, pending written-spec review  
**Date:** 2026-09-30  
**Target runtime:** MetaTrader 5 build 6230, VTMarkets-Demo  
**Execution authority:** Observer-only; no broker order submission, modification, cancellation, or position management

## 1. Purpose

This increment converts the existing offline-only EnterpriseEA contracts into verifiable MT5 runtime evidence without enabling trading. It adds read-only adapters for account identity, broker symbol specifications, active positions, pending orders, and deal history; persists versioned snapshots atomically; reconciles state after restart; compiles the MQL5 source with the installed MetaEditor; and records which requirements have offline, compiler, runtime, and broker-reconciliation evidence.

This increment does not grant entry permission. `EEA_StateCanAllowEntry` remains false, and the EA must remain safe when MT5 reports that terminal trading is allowed.

## 2. Existing evidence baseline

The current repository has 111 passing Python design-oracle tests. Offline evidence exists for:

- Phase 1 core config/state/event/storage contracts;
- Phase 2 S02 Break Retest closed-bar state machine;
- Phase 3 structural levels, trade economics, FTMO headroom, daily reset ledger, account risk reducer, portfolio budget, volume sizing, symbol registry, dry-run candidate gate, and ledger checkpoint contracts;
- Phase 4 expected-path observer, pending LIMIT/STOP lifecycle, pending checkpoint, and pending audit-chain contracts;
- isolated Telegram remote-mode schemas and command gate, while Telegram development remains paused.

This evidence does not prove MQL compilation, runtime behavior, broker completeness, Strategy Tester behavior, Paper readiness, or execution safety.

## 3. Scope

### 3.1 Included

1. Read-only account snapshot from MT5.
2. Read-only symbol discovery and broker specification snapshots.
3. Explicit canonical-to-broker symbol bindings; prefix/suffix matching may only produce suggestions.
4. Read-only snapshots of positions, active pending orders, and bounded deal history.
5. Fail-closed reconciliation status with source completeness and watermarks.
6. Atomic persistence of runtime snapshots and a narrow runtime checkpoint.
7. Startup/restart reconciliation and periodic refresh by timer.
8. `OnTradeTransaction` invalidation of cached reconciliation evidence followed by read-only refresh.
9. Audit events for initialization, refresh, material specification changes, degraded evidence, and shutdown.
10. MetaEditor compilation and MT5 observer runtime verification.
11. Documentation that distinguishes offline verification from compile/runtime/reconciliation evidence.

### 3.2 Excluded

- `OrderSend`, `OrderSendAsync`, `CTrade`, order modification, cancellation, close, partial close, BE, or trailing operations;
- broker execution tests or demo order placement;
- virtual fill simulation, slippage modeling, and Strategy Tester trading;
- dashboard, calendar, News Center, MCP AI runtime, or Telegram gateway;
- automatic inference of live risk policy, FTMO configuration, setup TTL, or pending-order drift thresholds;
- STOP LIMIT support;
- Paper or Live readiness claims.

## 4. Safety invariants

1. The EA starts only when `InpObserverOnly=true`.
2. Terminal or account trade permission never grants EA execution permission.
3. No source file in this increment may call an order-send, modify, delete, or position-close API.
4. New-entry permission remains false for every runtime state.
5. Missing, stale, conflicting, incomplete, or identity-mismatched evidence produces `UNKNOWN` or `BLOCKED`, never `READY`.
6. A broker request acknowledgement is not a cancellation/fill confirmation. This increment issues no such requests.
7. Account identifiers written to files or logs are opaque fingerprints; the numeric login and account holder name are not persisted.
8. Runtime files contain no credentials, tokens, or provider secrets.
9. Snapshot writes use same-directory temporary replacement. A torn or incompatible snapshot is preserved as evidence and cannot be treated as valid.
10. Restart never resets pending-order deadlines, event watermarks, or previously observed material-spec identity.
11. Telegram remains paused and cannot alter runtime state.

## 5. Architecture

### 5.1 Pure runtime evidence contracts

`Runtime/RuntimeEvidence.mqh` defines focused data structures and pure validation/comparison helpers:

- `EEA_RuntimeAccountSnapshot`
- `EEA_RuntimeSymbolSpec`
- `EEA_RuntimePositionRow`
- `EEA_RuntimeOrderRow`
- `EEA_RuntimeDealRow`
- `EEA_RuntimeReconciliationSnapshot`
- `EEA_RuntimeStatus`

The contract records `schema_version`, `config_version`, `snapshot_id`, UTC observation time, opaque account fingerprint, broker server, account currency/margin mode, source-completeness flags, source watermarks, and a reason code. Pure helpers validate finite numeric values, monotonic watermarks, unique row identities, volume invariants where applicable, and material symbol-spec equality.

### 5.2 MT5 adapters

`Runtime/AccountSnapshotAdapter.mqh` reads account and terminal properties. It derives an opaque, deterministic runtime fingerprint from server, account login, currency, and margin mode for local correlation. The raw login and account-holder name are not serialized.

`Runtime/SymbolSpecAdapter.mqh` reads broker symbol properties including digits, point, tick size/value, contract size, volume min/max/step, stop/freeze levels, trade mode, order mode, expiration mode, calculation mode, and currencies. It accepts only explicit canonical bindings for resolved status. Prefix/suffix discovery produces a non-authoritative suggestion list.

`Runtime/BrokerReconciliationAdapter.mqh` reads all active positions and orders for the account and a bounded deal-history window. It emits completeness flags independently for positions, orders, and deals. It records a deal watermark and rejects duplicate ticket identities or inconsistent observations. A bounded history snapshot may support current observer evidence but cannot claim complete lifetime lineage.

### 5.3 Persistence

`Storage/RuntimeEvidenceStore.mqh` serializes the narrow runtime evidence documents and writes them through `EEA_WriteAtomicText`.

Runtime layout:

```text
MQL5/Files/EnterpriseEA/
  current/
    account_snapshot.json
    symbol_registry.json
    broker_reconciliation.json
    runtime_status.json
  logs/
    audit.jsonl
```

Each document includes a schema version, document version, config version, snapshot ID, UTC timestamp, source, data quality, and reason code. Arrays use deterministic ordering by identity before serialization so restart comparisons are stable.

The initial increment uses a narrow parser/checkpoint compatibility check rather than a general-purpose JSON parser. It validates exact version/identity markers and forces a fresh broker read before reconciliation can become current. Stored evidence is never accepted as broker truth by itself.

### 5.4 Runtime coordinator

`Runtime/ObserverRuntime.mqh` owns initialization and refresh sequencing but not the global EA event handlers.

Startup sequence:

1. Validate observer-only configuration.
2. Read account and terminal identity.
3. Resolve configured canonical symbols through explicit bindings.
4. Check prior runtime-status compatibility.
5. Read active positions, active orders, and bounded deal history.
6. Validate identity, source completeness, and watermarks.
7. Persist current snapshots atomically.
8. Emit audit evidence.
9. Publish `OBSERVING`, `DEGRADED`, or `BLOCKED`; never publish execution readiness.

`EnterpriseEA.mq5` delegates:

- `OnInit` to runtime initialization after Phase 1 storage setup;
- `OnTimer` to periodic read-only refresh;
- `OnTradeTransaction` to mark broker evidence stale and schedule/perform a read-only refresh;
- `OnDeinit` to persist final observer status and release the timer.

`OnTick` remains free from broker-history scans and per-tick file writes.

## 6. Configuration

The observer runtime adds explicit inputs or validated defaults for:

- refresh interval in seconds, with a safe positive range;
- bounded history lookback in days;
- canonical symbol list;
- explicit broker symbol list with one-to-one positional binding;
- runtime evidence enabled flag, valid only in observer mode.

The first verified runtime fixture targets VTMarkets-Demo and must discover at least one explicitly bound visible symbol. No account policy, FTMO limit, base risk, pending TTL, or trading threshold is inferred from the demo account.

## 7. State and reason codes

Top-level runtime states:

- `OBSERVING`: current read-only evidence is valid for its declared bounded scope.
- `DEGRADED`: the EA remains operational as an observer, but one or more evidence sources are stale or incomplete.
- `BLOCKED`: identity, version, persistence, or validation failure prevents trustworthy observation.

Required reason codes include:

- `RUNTIME_EVIDENCE_CURRENT`
- `ACCOUNT_IDENTITY_UNAVAILABLE`
- `ACCOUNT_IDENTITY_CHANGED`
- `SYMBOL_BINDING_MISSING`
- `SYMBOL_BINDING_AMBIGUOUS`
- `SYMBOL_SPEC_INCOMPLETE`
- `SYMBOL_MATERIAL_SPEC_CHANGED`
- `POSITIONS_SOURCE_INCOMPLETE`
- `ORDERS_SOURCE_INCOMPLETE`
- `DEALS_SOURCE_INCOMPLETE`
- `DEAL_WATERMARK_REGRESSED`
- `RUNTIME_CHECKPOINT_MISSING`
- `RUNTIME_CHECKPOINT_INCOMPATIBLE`
- `RUNTIME_RECONCILIATION_REQUIRED`
- `RUNTIME_PERSISTENCE_FAILED`

A missing checkpoint on first startup is not broker evidence failure: the EA performs a fresh read, writes a new checkpoint, and records `RUNTIME_CHECKPOINT_MISSING`. An incompatible checkpoint makes the current cycle `BLOCKED` until a fresh read is successfully persisted under the current identity/version; the incompatible file must not silently authorize state.

## 8. Data flow

```text
MT5 account/symbol/order/position/history properties
  -> read-only adapters
  -> pure RuntimeEvidence validation
  -> runtime reconciliation status
  -> atomic current/*.json snapshots
  -> audit.jsonl events
  -> documentation/runtime verification artifacts
```

No arrow returns from the observer runtime to MT5 trade execution APIs.

## 9. Error handling

- Every adapter returns an explicit boolean/status plus reason code.
- Partial source success never collapses into a single successful reconciliation flag.
- Numeric NaN/Infinity, invalid volume steps, impossible min/max ranges, missing currencies, empty identity fields, and duplicate tickets fail closed.
- If persistence fails, in-memory evidence cannot be advertised as restart-safe.
- If `OnTradeTransaction` arrives, prior reconciliation becomes stale even if no relevant row is ultimately found; a fresh snapshot is required.
- If MetaEditor compilation fails, documentation remains `OFFLINE_VERIFIED`; no runtime-complete status is recorded.
- If runtime attachment or artifact collection cannot be automated, compilation evidence may be recorded separately, while `RUNTIME_OBSERVED` remains pending.

## 10. Testing strategy

### 10.1 Offline TDD

Add stdlib-only Python fixtures/oracles and tests before production MQL changes. Tests cover:

1. Valid account identity and unsupported/missing identity.
2. Explicit symbol binding versus suffix/prefix suggestions.
3. Material symbol-spec changes.
4. Complete empty account snapshot.
5. Active position/order/deal rows with unique identities.
6. Missing or incomplete source flags.
7. Duplicate tickets and deal-watermark regression.
8. Restart compatibility, identity mismatch, and forced fresh reconciliation.
9. Atomic-store/static boundaries.
10. Forbidden execution API scan across the entire EnterpriseEA source tree.

Each behavioral addition follows RED → GREEN → REFACTOR. The full existing suite must remain green.

### 10.2 Compiler evidence

Compile `EnterpriseEA.mq5` with MetaEditor build 6230 and retain the compiler log. Zero errors is required. Warnings must be reviewed; no warning that indicates truncation, uninitialized state, or unsafe conversion is accepted without a documented ruling.

### 10.3 Runtime evidence

Deploy source/includes into the installed terminal data path, run or attach the EA in observer mode, and inspect generated files. Verification requires:

- account server/currency/margin mode consistent with MT5;
- configured symbols resolved explicitly and their material specs recorded;
- active positions/orders reflected without creation of new orders;
- deal-history snapshot declares its bounded window and watermark;
- audit records initialization and refresh;
- restart produces a fresh broker read and no duplicate side effect;
- new-entry permission remains false;
- account order/position counts before and after verification are unchanged by the EA.

## 11. Acceptance criteria

1. All pre-existing 111 offline tests still pass.
2. New runtime-evidence tests fail before implementation and pass afterward.
3. Static checks find no execution API in the project and confirm runtime modules are observer-only.
4. MetaEditor build 6230 compiles the EA with zero errors.
5. The EA runs against VTMarkets-Demo in observer mode and writes versioned runtime evidence.
6. A restart forces fresh read/reconciliation and does not use persisted evidence as broker truth.
7. No order, position, or account balance change is caused by the verification run.
8. Documentation accurately marks each component as one of: `OFFLINE_VERIFIED`, `MQL_COMPILED`, `RUNTIME_OBSERVED`, `BROKER_RECONCILED_BOUNDED`, `PAPER_EXCLUDED_PERMANENTLY`, or `NOT_IMPLEMENTED`.
9. Phase 3/4 are not marked complete merely because the adapter compiles or observes a bounded history window.

## 12. Traceability impact

- REQ-013/014/016/017 gain compiler/runtime evidence for broker/account/symbol snapshots and bounded reconciliation.
- REQ-021 gains observation of active pending orders and restart evidence, but no cancellation adapter, transaction-driven lifecycle integration, or Paper proof.
- TC-009/010 gain actual broker metadata observation but still require broader runtime scenarios.
- TC-016 gains read-only stop/freeze/volume/order-mode evidence but no execution rejection proof.
- TC-030 gains runtime checkpoint/restart evidence for observer snapshots, not full trade lifecycle restoration.
- TC-046–051 remain offline-verified only until pending-order runtime integration and Paper scenarios exist.

## 13. Evidence classification after this increment

If every acceptance criterion passes:

- Existing pure modules: `OFFLINE_VERIFIED`, plus `MQL_COMPILED` if included in a dedicated compile harness or the shell build.
- Runtime account/symbol/reconciliation adapters: `OFFLINE_VERIFIED`, `MQL_COMPILED`, `RUNTIME_OBSERVED`.
- Bounded positions/orders/deals snapshot: `BROKER_RECONCILED_BOUNDED`, explicitly not full historical lineage.
- Pending-order execution/cancellation: `NOT_IMPLEMENTED`.
- Virtual/Paper execution and Paper soak: `PAPER_EXCLUDED_PERMANENTLY`; Strategy Tester trading and Live remain `NOT_AUTHORIZED` until the controlled-live gates are satisfied.
- Dashboard, News Center, MCP AI runtime, Telegram gateway: `NOT_IMPLEMENTED` or paused as documented.

## 14. Operational constraints

The current folder is not a Git repository. Therefore this increment cannot use a Git worktree or produce commits unless a repository is initialized by an explicit user decision. Implementation may proceed in place after preserving a file-level baseline and recording changed files. No publish, push, live trading, or destructive broker operation is permitted.
