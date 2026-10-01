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

The implementation is market-only until pending-order runtime is complete and separately evidenced. The allowed operation set is `SUBMIT_MARKET` for BUY/SELL and `MODIFY_PROTECTIVE` for an existing position. `SUBMIT_PENDING`, `CANCEL_PENDING`, and pending-order protective modification are hard-denied before any broker request. This does not reduce the seven mandatory controlled-live gates.

The current increment also adds compile-covered read-only account financial and trade-quote/margin evidence contracts, plus a standalone fail-closed controller/kill-switch contract. None of these contracts is an authorization substitute; dispatch, durable control-state loading, risk decision lineage, restart recovery, and retained target-runtime evidence remain required.

Risk release is now an explicit contract: `REVIEWABLE_CANDIDATE` cannot authorize execution, and only a fresh `RISK_APPROVED` decision with complete provenance can be used to construct a future intent. The execution gate additionally rejects intents that lack this lineage.

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
