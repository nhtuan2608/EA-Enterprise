# Paperless Controlled-Live Evidence and Authorization Plan

> Documentation and evidence plan only. It does not authorize live trading, create a Paper ledger, or replace the execution-adapter implementation plan.

**Goal:** Define a paperless controlled-live path whose authorization is evidence-based, manually approved, fail-closed, reversible, and auditable.

**Spec:** `EnterpriseEA/docs/superpowers/specs/2026-10-01-paperless-controlled-live-design.md`

## Non-negotiable constraints

- The Paper ledger is permanently excluded. Do not add Paper, virtual, simulated, or shadow execution as a fallback or evidence substitute.
- The default remains `IMPLEMENTED_DISABLED_BY_DEFAULT`; no lifecycle or callback path may infer authorization.
- Paperless controlled-live remains `NOT_AUTHORIZED` until every mandatory gate has retained evidence.
- A successful compile, offline test, bounded tester run, or demo run does not by itself establish live readiness.
- Secrets and raw account-holder identity must not appear in retained evidence.
- `EXECUTION_UNKNOWN`, stale reconciliation, identity mismatch, audit failure, kill-switch failure, or rollback failure blocks new entries and requires manual review.

## Current execution scope

The execution contract represents the full operation vocabulary: `SUBMIT_MARKET`, `SUBMIT_PENDING`, `MODIFY_PROTECTIVE`, `CANCEL_PENDING`, `CLOSE`, `PARTIAL_CLOSE`, `BREAK_EVEN`, and `TRAILING`. Selecting full scope does not enable any operation. Each operation remains hard-denied until its own broker capability, reconciliation, rollback and audit evidence is retained. The first controlled runtime may still use a narrower allowlist while full-scope evidence is accumulated. This does not reduce the seven mandatory controlled-live gates.

The terminal policy selector uses versioned profiles `FTMO_1_STEP`, `FTMO_2_STEP`, and `BALANCE_BASED_FTMO_V1`; no profile is silently selected. Both daily and overall profit-target continuation overrides default to `true`, but they only prevent a profit-target stop and never override loss floors, exposure, margin, stale reconciliation, kill switch, authorization expiry or `EXECUTION_UNKNOWN`. Operators enter authorization times in GMT+7; the system stores and compares UTC.

The current increment also adds compile-covered read-only account financial and trade-quote/margin evidence contracts, plus a standalone fail-closed controller/kill-switch contract. None of these contracts is an authorization substitute; dispatch, durable control-state loading, risk decision lineage, restart recovery, and retained target-runtime evidence remain required.

Risk release is now an explicit contract: `REVIEWABLE_CANDIDATE` cannot authorize execution, and only a fresh `RISK_APPROVED` decision with complete provenance can be used to construct a future intent. The execution gate additionally rejects intents that lack this lineage.

## Implementation Tasks

### Task 1: Durable controller and kill-switch state

Implement a versioned, redacted controller-state document with atomic write, strict load/validation, revision monotonicity, exact operation scope, operator reference, valid window, and fail-closed defaults. A missing, corrupt, stale, or identity-mismatched state must reject new requests. Add restart/readability tests without connecting it to broker mutation yet.

### Task 2: Risk decision to execution-intent lineage

Build the pure bridge that accepts only a fresh `RISK_APPROVED` decision and constructs a market-only execution intent carrying candidate, setup, policy, account, reconciliation, symbol, quote, portfolio, sizing, expiry, and idempotency provenance. Reject review-only candidates, stale evidence, mismatched fingerprints, non-finite values, and unsupported pending operations. Add unit/static tests and persist all lineage fields.

### Task 3: Runtime strategy and two-pass risk integration

Integrate closed-bar S02 observation, structural levels, current quote/cost/margin evidence, account-wide reconciliation, preliminary budget/sizing, final loss/margin/economics/FTMO/portfolio recheck, and explicit risk decision output. Keep automatic execution disabled while retaining restart-safe candidate and decision evidence.

### Task 4: Controlled dispatch, reconciliation, and recovery

Add one explicit operator/controller dispatch path for the market-only scope. Require durable pre-send intent, controller state, risk decision, authorization, fresh reconciliation, idempotency, and kill-switch checks. Persist broker acknowledgement, reconcile positions/orders/deals, handle unknown/timeout/restart without silent retry, and retain a redacted evidence bundle.

### Task 5: Target-runtime gate review and activation

Compile the exact target build, run the controlled target-runtime verification, test kill-switch and rollback, collect retained pre/post/restart evidence, bind the approved live account/symbol policy and manual authorization window, and execute only the exact bounded market-only scope. Mark `AUTHORIZED_CONTROLLED_LIVE` only after every gate passes; otherwise remain `NOT_AUTHORIZED`.

## Gate work

### 1. Runtime compile gate

- Bind the evidence to the exact source revision, configuration, target terminal/build, and adapter surface.
- Retain MetaEditor output showing `0 errors, 0 warnings`.
- Record whether the evidence covers the integrated adapter or only an observer/read-only build.
- Mark the gate open if the output is missing, stale, or not reproducible.

### 2. Demo/retained-evidence gate

- For any proposed operation that relies on demo or retained runtime behavior, retain the controlled run, pre/post snapshots, acknowledgement, reconciliation, restart/timeout/unknown result, and operator review.
- Distinguish synthetic/offline fixtures, bounded tester evidence, retained demo evidence, and live evidence by label and scope.
- If applicable demo/retained evidence is absent or not retained, keep `RUNTIME_EVIDENCE_PENDING` and do not authorize.

### 3. Risk-policy gate

- Select and approve a versioned account/symbol risk policy.
- Bind policy version, limits, volume/price constraints, broker symbol fingerprint, account fingerprint, and reconciliation watermark to each intent.
- Reject the gate for missing policy, stale reconciliation, account/server mismatch, invalid symbol specification, or unresolved exposure.

### 4. Manual-authorization gate

- Prepare a human review record naming the exact account/server, symbols, operation scope, maximum exposure, policy version, evidence references, and start/end time.
- Require explicit approval after reviewing all open gates.
- Expire the authorization on window end, identity/configuration change, kill-switch activation, or any unknown state.

### 5. Kill-switch gate

- Verify a reachable control that rejects new execution requests and leaves the system fail-closed.
- Test activation and recovery in the target runtime; retain timestamps, scope, result, and operator reference.
- Treat an unreachable, untested, or ambiguous kill switch as a hard block.

### 6. Rollback gate

- Exercise disable/rollback for request acknowledgement without confirmation, partial execution, timeout, terminal restart, callback race, and `EXECUTION_UNKNOWN`.
- Confirm that rollback does not silently retry or modify unrelated existing orders/positions.
- Retain before/after exposure, reconciliation, audit, and operator-review evidence.

### 7. Audit gate

- Verify durable redacted records for intent, correlation/idempotency, preflight, policy, authorization, request acknowledgement, reconciliation, kill-switch actions, rollback, and final disposition.
- Verify append/flush behavior, sequence or fingerprint continuity, and restart readability.
- Block authorization if any required link is missing or cannot be correlated to the exact operation.

## Final review and status

The final reviewer records one of:

- `NOT_AUTHORIZED`: any gate is open, stale, ambiguous, or lacks retained evidence;
- `AUTHORIZED_CONTROLLED_LIVE`: every required gate is evidenced, manually approved, and within its authorization window;
- `REVOKED`: authorization was withdrawn or a fail-closed condition occurred.

The current documented state is `NOT_AUTHORIZED`. The plan is complete only when the evidence package is reviewable and all seven gates are explicitly marked pass; even then, authorization is limited to the exact manually approved scope and window. No document update may describe live trading as ready before that review.
