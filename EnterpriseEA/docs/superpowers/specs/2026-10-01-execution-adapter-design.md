# Disabled-by-Default Execution Adapter Design

**Status:** Design approved; implementation and controlled-live evidence remain incomplete
**Date:** 2026-10-01  
**Target:** MetaTrader 5 build 6230, VTMarkets-Demo  
**Paper ledger:** Permanently excluded. No paper or virtual execution ledger will be added, maintained, or used as a readiness substitute.
**Default authority:** Observer-only; execution disabled by default.

## Purpose

Add a real but disabled-by-default execution boundary for placing pending/market orders, modifying protective SL/TP, and cancelling pending orders. The adapter must be callable only after current account-wide reconciliation, symbol-spec validation, idempotency checks, audit persistence, and a fail-closed execution gate. It must not create a Paper ledger and must not be enabled against live trading as part of this increment. The later paperless controlled-live route is governed by the mandatory gates in [the controlled-live design](2026-10-01-paperless-controlled-live-design.md); it is not implied by this adapter design.

## Scope

Included:

- Versioned execution intent/result contracts.
- Read-only preflight gate binding account, server, canonical/broker symbol, config, symbol fingerprint, risk decision and fresh reconciliation snapshot.
- MQL5 adapter wrappers for market/pending submit, SL/TP modification and pending cancellation.
- Idempotency/correlation guard and durable intent/ack audit records.
- Reconciliation after every broker request; request acknowledgement is never fill/cancel confirmation.
- Restart/timeout/race state `EXECUTION_UNKNOWN` that blocks new entries until fresh broker reconciliation.
- Demo-only controlled test mode with `InpExecutionEnabled=false` default and no automatic request in startup/timer/chart events.
- Offline TDD tests, MQL compile verification and documentation/traceability updates.

Excluded:

- Paper/virtual execution ledger, permanently and architecturally excluded.
- Automatic strategy signal generation.
- Telegram/AI direct execution.
- Live enablement or go-live authorization.
- Any order operation while `InpExecutionEnabled=false`.

## Safety invariants

1. `InpExecutionEnabled=false` is the default and causes every execution request to be rejected before any MT5 trade API call.
2. `InpObserverOnly=false` remains a startup refusal unless a separate future execution profile explicitly enables it; this increment does not enable that profile.
3. No execution request is accepted without fresh account/positions/orders/deals reconciliation and a valid symbol specification.
4. A unique correlation ID and idempotency key are mandatory; an already accepted key is rejected as duplicate without a second broker request.
5. `OrderSend`/modify/delete return values are request acknowledgements only. The adapter must re-read active orders/positions/deal history before declaring a fill, modification, or cancellation confirmed.
6. Timeout, terminal restart, missing history, callback race, account identity change or stale snapshot yields `EXECUTION_UNKNOWN`, preserves entries blocked, and never silently retries.
7. Account login/name, credentials and provider secrets are never serialized.
8. No Paper ledger is created or implied.
9. The execution adapter is never called from `OnTick`, timer refresh, symbol panel Refresh, or automatic startup reconciliation.
10. Existing orders/positions are never modified by verification unless a future explicit controlled execution test invokes the adapter with a valid intent.

## Paperless controlled-live boundary

Paperless controlled-live means broker execution through this adapter without a Paper ledger. It is a separately gated operating mode, not a status claim and not a replacement for evidence. The mode cannot be authorized until every applicable gate below is closed with retained evidence:

1. **Runtime compile:** the exact target source and configuration compile in the target MetaEditor build with `0 errors, 0 warnings`; the build identity is retained.
2. **Demo/retained evidence:** controlled demo evidence and retained runtime evidence are collected when applicable. Missing, non-retained, synthetic-only, or bounded evidence leaves the gate open.
3. **Risk policy:** a versioned, approved account/symbol risk policy is bound to the execution intent and its current reconciliation snapshot.
4. **Manual authorization:** an identified human explicitly authorizes the exact account/server, symbols, scope, and time window after reviewing the evidence. No automatic or inferred authorization is valid.
5. **Kill switch:** a reachable, tested kill switch disables new execution requests and leaves the system fail-closed; its test evidence is retained.
6. **Rollback:** a tested disable/rollback procedure covers request acknowledgement, partial execution, timeout, restart, race, and `EXECUTION_UNKNOWN` without silent retry.
7. **Audit:** redacted durable audit records link intent, authorization, risk decision, request acknowledgement, reconciliation, kill-switch/rollback events, and operator identity or authorization reference.

If any gate is missing or stale, paperless controlled-live remains `NOT_AUTHORIZED`. A compile result, a demo result, an offline test, or the existence of an adapter alone never establishes live readiness.

## Contracts

### Execution intent

`EEA_ExecutionIntent` contains:

- `schema_version`, `intent_id`, `correlation_id`, `idempotency_key`;
- `config_version`, `account_fingerprint`, `broker_server`;
- `canonical_symbol`, `broker_symbol`, `symbol_fingerprint`;
- released risk-decision lineage (`candidate_id`, `risk_decision_id`, policy,
  quote, portfolio, reconciliation, volume, and projected loss);
- `action` = `SUBMIT_MARKET`, `SUBMIT_PENDING`, `MODIFY_PROTECTIVE`, `CANCEL_PENDING`;
- order type, direction, requested volume, entry, SL, TP, expiration;
- `reconciliation_snapshot_id`, `reconciliation_observed_at_utc`, `intent_created_at_utc`;
- preflight gate result and reason code.

The released-submit boundary also receives the immutable `EEA_RiskDecision`.
Before the ordinary execution gate runs, it must validate that the decision is
`RISK_APPROVED`/`RELEASED`, current, and bound to the intent lineage. A matching
`risk_decision_status` string alone is not authorization evidence.

`Runtime/ExecutionIntentBuilder.mqh` is the only approved construction path for
a market intent: it rejects review-only/expired decisions, pending actions,
identity mismatches, invalid geometry, and incomplete idempotency fields.

### Result

`EEA_ExecutionResult` contains:

- intent/correlation/idempotency identifiers;
- `request_sent`, `request_retcode`, `request_ticket`;
- `confirmation_state` = `NOT_SENT`, `REQUEST_ACCEPTED`, `CONFIRMED`, `REJECTED`, `EXECUTION_UNKNOWN`;
- fresh post-request snapshot ID/watermark when available;
- reason codes and observed time.

## Gate and state flow

```text
DISABLED
  -> PREFLIGHT_REQUIRED
  -> PREFLIGHT_ACCEPTED
  -> REQUEST_SENT
  -> RECONCILIATION_REQUIRED
  -> CONFIRMED | REJECTED | EXECUTION_UNKNOWN
```

Only an explicit caller can request the transition out of `DISABLED`; startup, timer, chart panel and external transaction callbacks cannot do so. `EXECUTION_UNKNOWN` cannot be cleared by a duplicate request; only fresh broker reconciliation can produce a new decision.

## Broker adapter boundary

Create `Runtime/ExecutionAdapter.mqh` with these functions:

```mql5
bool EEA_ExecutionPreflight(const EEA_ExecutionIntent &intent,
                            const EEA_RuntimeAccountSnapshot &account,
                            const EEA_RuntimeReconciliationSnapshot &reconciliation,
                            const EEA_RuntimeSymbolSpec &symbol,
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

Each mutating function first checks the gate and idempotency guard. It uses the corresponding MT5 trade API only after explicit preflight acceptance, writes `EXECUTION_REQUESTED`, and immediately requires an authoritative reconciliation callback supplied by the caller/observer coordinator. It does not invent confirmation from `MqlTradeResult` alone.

## Testing and activation

- Python oracle tests cover disabled default, missing/stale/mismatched reconciliation, wrong symbol spec, duplicate idempotency, allowed demo preflight, request acknowledgement versus confirmation, timeout/unknown, cancel/fill race and redaction.
- MQL static tests prove no adapter call path is reachable from startup/timer/OnTick/panel events and that no Paper ledger files or contracts exist.
- MetaEditor build 6230 must report `0 errors, 0 warnings`.
- The first controlled demo operation requires a separate explicit user confirmation after compile and preflight verification. No operation is automatically executed by this increment.
- Paperless controlled-live remains blocked until the mandatory runtime compile, applicable demo/retained evidence, risk-policy, manual-authorization, kill-switch, rollback, and audit gates are independently evidenced and reviewed.
- No operation is automatically executed by this increment, and no live readiness is claimed.

## Traceability

- Pending submission/modify/cancel changes from `NOT_IMPLEMENTED` to `IMPLEMENTED_DISABLED_BY_DEFAULT` only after source/tests compile.
- Paper ledger is `PAPER_EXCLUDED_PERMANENTLY`; there is no Paper parity gate.
- Paperless controlled-live and go-live remain `NOT_AUTHORIZED` until every mandatory gate is independently evidenced; current bounded or synthetic evidence does not close those gates.
