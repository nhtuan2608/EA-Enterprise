# Paperless Controlled-Live Design

**Status:** Design only; `NOT_AUTHORIZED`
**Date:** 2026-10-01
**Relationship:** Governs any future controlled-live use of the disabled-by-default execution adapter.

## Decision and boundary

The Paper ledger is permanently excluded. No paper, simulated, virtual, or shadow execution ledger will be implemented, maintained, or treated as a substitute for broker evidence. The only future execution route is paperless: an explicitly authorized broker operation through the fail-closed execution adapter.

Paperless controlled-live is not live readiness by default. It is an operating mode that may be entered only after every applicable gate below is closed with retained, reviewable evidence. Offline tests, source inspection, a successful compile, a demo result, or the existence of an adapter alone never authorizes live trading.

## Initial operation scope

The first controlled-live scope is deliberately market-only:

- `SUBMIT_MARKET` may cover only BUY/SELL market requests after the full gate matrix passes.
- `MODIFY_PROTECTIVE` may cover an existing position (`position_ticket > 0`) only.
- `SUBMIT_PENDING`, `CANCEL_PENDING`, and protective modification of a pending order are hard-denied with `PENDING_RUNTIME_NOT_IMPLEMENTED`.
- LIMIT/STOP/STOP_LIMIT lifecycle, checkpoint, expiry, partial-fill, restart, and broker-event handling remain out of scope until separately implemented and evidenced.

This scope restriction is an additional execution boundary, not a waiver of any required risk, authorization, kill-switch, rollback, reconciliation, or audit gate.

## Implemented prerequisite contracts

The observer shell now has compile-covered, read-only boundaries for account financial state (`balance`, `equity`, `margin`, `margin_free`) and current trade quote/margin/loss evidence. A separate controller contract defaults to `kill_active=true` and requires a valid operator, revision, exact scope, and time window before it can allow a request. These contracts are prerequisites only: they are not yet wired into an execution dispatch path and do not change the documented `NOT_AUTHORIZED` state.

## Required gate matrix

| Gate | Required evidence | Current status / blocking rule |
| --- | --- | --- |
| Runtime compile | Exact target source/configuration compiled with the target MetaEditor build, `0 errors, 0 warnings`, plus build identity and retained output | `RUNTIME_EVIDENCE_PENDING` for controlled-live until adapter-specific evidence is retained; an observer compile alone is insufficient |
| Demo/retained evidence, if applicable | Controlled demo evidence and/or retained runtime evidence for the behavior relied upon: preflight, acknowledgement, reconciliation, restart/timeout/unknown handling, and side-effect snapshots | `RUNTIME_EVIDENCE_PENDING`; bounded or synthetic evidence does not close a required runtime gate |
| Risk policy | Versioned approved account/symbol policy, limits, sizing inputs, broker constraints, and current reconciliation binding | `NOT_AUTHORIZED` until reviewed and bound to the exact intent |
| Manual authorization | Explicit human approval naming account/server, symbols, scope, time window, risk policy version, and evidence references | `NOT_AUTHORIZED`; no implicit, automated, or stale approval |
| Kill switch | Reachable control that rejects new requests, fails closed, and has a retained test record | `NOT_AUTHORIZED` until tested in the target runtime |
| Rollback | Tested disable/rollback procedure for acknowledgement, partial execution, timeout, restart, race, and `EXECUTION_UNKNOWN`; no silent retry | `NOT_AUTHORIZED` until the procedure and result are retained |
| Audit | Durable, redacted records linking intent, risk decision, authorization, request result, reconciliation, operator action, kill-switch events, and rollback | `NOT_AUTHORIZED` until the complete chain is reviewable |

All gates are mandatory. “If applicable” means that evidence must be supplied whenever the proposed route relies on that demo or retained runtime behavior; it does not permit an unreviewed evidence gap to be treated as a pass.

## State rules

- `PAPER_EXCLUDED_PERMANENTLY` is the permanent state for the Paper ledger boundary.
- `IMPLEMENTED_DISABLED_BY_DEFAULT` describes adapter availability, not authorization.
- `RUNTIME_EVIDENCE_PENDING` describes missing or non-retained runtime evidence.
- `NOT_AUTHORIZED` is the required state whenever any gate is open, stale, ambiguous, or not bound to the exact operation.
- An `AUTHORIZED_CONTROLLED_LIVE` state may be recorded only after a manual gate review confirms all required evidence and the authorization window is active. This document does not assert that state.
- `EXECUTION_UNKNOWN` blocks new entries and requires fresh broker reconciliation; it is never resolved by retrying the same intent.

## Operational sequence

```text
DISABLED
  -> evidence and gate review
  -> explicit manual authorization
  -> one bounded operation in the authorized window
  -> broker acknowledgement
  -> authoritative reconciliation
  -> confirmed result or EXECUTION_UNKNOWN
  -> audit and close/rollback review
```

Startup, timer, tick, chart refresh, and transaction callbacks cannot grant authorization or start a controlled-live operation. The kill switch must remain available throughout the window. Any identity change, stale snapshot, missing history, timeout, race, or audit failure fails closed and invokes the rollback/unknown procedure.

## Evidence and audit requirements

Retain, at minimum, the redacted records for:

- exact build/source/configuration identity and compile output;
- preflight inputs, reconciliation watermark, symbol fingerprint, risk-policy version, and decision;
- manual authorization reference and authorized scope/window;
- intent, correlation, idempotency, request acknowledgement, and broker ticket where available;
- post-request active-order/position/deal evidence and the resulting confirmation state;
- kill-switch test, rollback actions, unknown-state handling, and final operator review.

Never retain credentials, raw account-holder identity, or provider secrets. A retained artifact must be bound to the account fingerprint, broker server, configuration version, and evidence timestamp without exposing secrets.

## Explicit non-claims

This design does not claim that live trading is ready, authorized, safe, or currently active. Existing offline, compile, tester, or bounded observer evidence must remain labeled with its scope and cannot be promoted to live evidence without passing this gate matrix.
