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

The current increment also adds compile-covered read-only account financial and trade-quote/margin evidence contracts, plus a standalone fail-closed controller/kill-switch contract. None of these contracts is an authorization substitute. The controlled-live orchestration now exists in `Integration/ControlledLiveRuntime.mqh`: it calculates account-wide stress exposure, builds fresh dry-run evidence, performs the strict two-pass release, persists the released decision before building an intent, loads identity-bound authorization, and calls the market-only adapter only after the controller and all release checks pass. Target-runtime demo/live evidence, restart outcome recovery, and retained gate evidence remain required.

Risk release is now an explicit contract: `REVIEWABLE_CANDIDATE` cannot authorize execution, and only `EEA_RiskDecisionReleaseFromReview` can promote a fresh second-pass bundle to `RISK_APPROVED/RELEASED` after runtime/account/quote/policy/portfolio/symbol rechecks and complete provenance. Direction, entry, SL, TP, budget, and reward/risk are carried into the release and bound by `ExecutionIntentBuilder`. The execution gate additionally rejects intents that lack this lineage. The producer is compile-covered; lifecycle collection and operator dispatch remain open in Tasks 3–4.

## Implementation Tasks

### Task 1: Durable controller and kill-switch state

Implement a versioned, redacted controller-state document with atomic write, strict load/validation, revision monotonicity, exact operation scope, operator reference, valid window, and fail-closed defaults. A missing, corrupt, stale, or identity-mismatched state must reject new requests. Add restart/readability tests without connecting it to broker mutation yet.

### Task 2: Risk decision to execution-intent lineage

Build the pure bridge that accepts only a fresh `RISK_APPROVED` decision and constructs a market-only execution intent carrying candidate, setup, policy, account, reconciliation, symbol, quote, portfolio, sizing, expiry, and idempotency provenance. Reject review-only candidates, stale evidence, mismatched fingerprints, non-finite values, and unsupported pending operations. `Runtime/ExecutionIntentBuilder.mqh` now provides this strict bridge and binds the intent back to the released decision; lifecycle invocation and persistence-before-dispatch remain in Tasks 3–4. Add unit/static tests and persist all lineage fields.

### Task 3: Runtime strategy and two-pass risk integration

Integrate closed-bar S02 observation, structural levels, current quote/cost/margin evidence, account-wide reconciliation, preliminary budget/sizing, final loss/margin/economics/FTMO/portfolio recheck, and explicit risk decision output. `Runtime/StrategyCandidateRuntime.mqh` now provides a timer-driven, M5 closed-bar/ATR adapter using a bounded lookback break and pinned S02 key level; it is explicitly disabled by default and rejects the offline research config. `Storage/StrategyCandidateStore.mqh` provides identity-bound atomic candidate checkpoints with stale/corrupt/mismatch fail-closed load statuses. `Integration/ControlledLiveRuntime.mqh` now wires the live profile through current quote, structural levels, FTMO headroom, account-wide existing-position/order stress, portfolio budget, volume sizing, economics, strict two-pass release, risk-decision persistence, intent construction, identity-bound authorization, controller scope, market submit, and reconciliation. Runtime risk inputs are explicit operator inputs and remain zero/invalid by default; no execution occurs unless the separate live profile is armed.

### Task 4: Controlled dispatch, reconciliation, and recovery

Add one explicit operator/controller dispatch path for the market-only scope. Require durable pre-send intent, controller state, risk decision, authorization, fresh reconciliation, idempotency, and kill-switch checks. Persist broker acknowledgement, reconcile positions/orders/deals, handle unknown/timeout/restart without silent retry, and retain a redacted evidence bundle. The bounded dispatch path is now integrated; restart/timeout/unknown recovery evidence and target-terminal execution verification remain open gates.

### Task 5: Target-runtime gate review and activation

Compile the exact target build, run the controlled target-runtime verification, test kill-switch and rollback, collect retained pre/post/restart evidence, bind the approved live account/symbol policy and manual authorization window, and execute only the exact bounded market-only scope. Mark `AUTHORIZED_CONTROLLED_LIVE` only after every gate passes; otherwise remain `NOT_AUTHORIZED`.

### Task 6: Neutral observer UI presentation

Refine the chart presentation without changing runtime authority or execution behavior. Add a shared low-saturation palette, opaque bounded surfaces, explicit font/spacing/z-order/corner styling, clipped/split evidence rows, semantic status colors, and deterministic cleanup for main/settings/dashboard objects. Keep `EXECUTION_DISABLED`, `NOT_AUTHORIZED`, blocked-entry, proposal-only, audit, GMT+7/UTC, and context-only copy visible. Limit rendered rows to the bounded card capacity; Settings provides Prev/Next paging plus a visible/total summary without changing stored row indices or selection state. The readability follow-up increases the panel width, body/control font sizes, row spacing, and card padding; same-view overlay renders reuse existing objects while dynamic Settings/Dashboard rows are cleared before rebinding. State-bearing buttons now use a muted green fill for ON/selected/confirmed and a near-black fill for OFF/unselected, while navigation/action buttons remain neutral. Settings/Dashboard are created only in live terminal contexts (never Strategy Tester/optimization), and refresh is timer-owned with no manual Refresh control. Add static regression tests for the presentation contract and retain exact-target MetaEditor compile evidence. A terminal screenshot/runtime check remains a separate verification item when the target window is available.

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

### UI increment evidence (2026-10-03)

Task 6 source/test changes are isolated to the observer presentation layer and its contract tests. The readability and render-lifecycle follow-up remains presentation-only: it does not change policy persistence, runtime authority, or execution behavior. State-bearing controls use explicit ON/OFF fills (`EEA_PANEL_ON_COLOR` / `EEA_PANEL_OFF_COLOR`) and update immediately after selection changes. The current verification records `296` Python tests passing and exact-target MetaEditor output `Result: 0 errors, 0 warnings` (latest compile on 2026-10-03; target runtime evidence is observing with resolved broker mappings). Settings/Dashboard click routing now calls `ChartRedraw` immediately in both one-click branches. This does not close any controlled-live gate or authorize live trading; target-terminal visual/runtime evidence remains pending when the terminal window is targetable.

### Controlled-live orchestration evidence (2026-10-03)

The live profile is now a separate, opt-in path: `InpObserverOnly=true`, `InpExecutionEnabled=false`, and `InpLiveTradeArmed=false` remain the defaults. A non-observer start requires both execution and arm inputs. `Storage/LiveAuthorizationStore.mqh` requires all authorization gates, exact config/account/server/broker-symbol identity, and the candidate ID; `Storage/RiskDecisionStore.mqh` persists the released decision before the intent is sent. `Storage/ExecutionRecoveryStore.mqh` restores an acknowledged-but-unreconciled result after restart and keeps dispatch blocked until fresh reconciliation confirms it. Observer status remains entry-blocked; only a local execution status is relaxed after release, authorization, controller scope, and fresh evidence have passed. The current verification records `299` Python tests and exact-target MetaEditor output `Result: 0 errors, 0 warnings`. This adds an executable route but does not close the seven controlled-live gates or claim live readiness.
