# Paperless Controlled-Live Design

**Status:** Design only; `NOT_AUTHORIZED`  
**Date:** 2026-10-01  
**Relationship:** Governs any future controlled-live use of the disabled-by-default execution adapter.

## Decision and boundary

The Paper ledger is permanently excluded. No paper, simulated, virtual, or shadow execution ledger will be implemented, maintained, or treated as a substitute for broker evidence. The only future execution route is paperless: an explicitly authorized broker operation through the fail-closed execution adapter.

Paperless controlled-live is not live readiness by default. It is an operating mode that may be entered only after every applicable gate below is closed with retained, reviewable evidence. Offline tests, source inspection, a successful compile, a demo result, or the existence of an adapter alone never authorizes live trading.

## Runtime identity and symbols

Account/server identity is discovered from the terminal at attachment and refresh time; operators do not type a login or broker server. Canonical symbols come from `InpCanonicalSymbols` and the chart selection panel; each selected canonical symbol is re-resolved against current broker symbols and material specifications. Identity, mapping, or specification change invalidates authorization and requires fresh reconciliation.

## Risk policy selector

Risk policy is selected only from versioned, pre-defined profiles. The terminal panel may display a compact selector and Apply control; Telegram/AI may submit a proposal, but neither may edit thresholds or activate a policy without explicit confirmation, fresh reconciliation, and an audit record.

The initial selector profiles are:

- `FTMO_1_STEP`: daily loss 3%, overall loss 10%, high-water/trailing floor rules as defined by the FTMO profile contract.
- `FTMO_2_STEP`: daily loss 5%, overall loss 10%, two-step reset/high-water rules as defined by the FTMO profile contract.
- `BALANCE_BASED_FTMO_V1`: balance-based policy profile with versioned limits and safety buffer; it is not inferred from the demo account.

No profile is silently selected. Until a profile is explicitly selected, risk is `UNKNOWN`, new entries are blocked, and execution remains disabled.

### Profit-target continuation override

Each selected profile may define both a daily and overall profit target. The operator can set `continue_after_daily_profit_target` and `continue_after_overall_profit_target` from the terminal selector; the default for both is `true` as requested. Telegram/AI may propose these boolean overrides but cannot activate them without the same confirmation/reconciliation/audit flow.

The override only prevents a profit-target stop. It never overrides daily/overall loss floors, FTMO headroom, maximum risk, margin, exposure, stale reconciliation, symbol mismatch, kill switch, authorization expiry, or `EXECUTION_UNKNOWN`. A target override applies only to new intents after its revision is committed; it never mutates an existing intent or pending order.

## Observer panel presentation contract

The terminal chart panel is a read-only presentation layer for runtime evidence and staged policy proposals. Presentation changes must not change authorization, risk, audit, persistence, selection, or execution behavior.

- Main, Settings, and Dashboard views use bounded opaque surfaces with explicit pixel geometry, shared spacing, font, z-order, cleanup prefix, and chart corner. Text is clipped to a bounded label length and long status/account/telemetry strings are split into labeled rows.
- The palette is neutral and low-saturation: dark blue-gray background/surfaces, off-white primary text, cool-gray secondary text, muted blue accent, muted green for healthy/reconciled state, amber for degraded/pending state, and muted red only for blocked/error state. Color never represents authorization by itself.
- The main view keeps `EXECUTION_DISABLED`, `NOT_AUTHORIZED`, and blocked-entry state visible. Settings keeps proposal-only, confirmation, GMT+7-to-UTC, durable persistence, and audit copy visible. Dashboard remains read-only and displays financial, reconciliation, watermark, freshness, symbol, and live-blocking evidence.
- At most `EEA_PANEL_VISIBLE_ROWS` symbol rows are rendered per bounded card. Settings provides Prev/Next viewport controls and a visible/total summary so every stored symbol row remains operator-addressable; paging is presentation-only and does not change stored selection or runtime symbol indices.
- UI lifecycle must remove stale objects on initialization, overlay transitions, and destruction. The panel must not use `Comment()` or introduce broker mutation APIs, Paper behavior, or any path that could imply live authorization.

The visual contract is accepted only after static tests and exact-target MetaEditor compilation pass. A compile result does not substitute for a target-terminal screenshot/runtime check.

## Full operation scope and staged authorization

The execution contract represents the full operation vocabulary:

- `SUBMIT_MARKET` BUY/SELL;
- `SUBMIT_PENDING` LIMIT/STOP;
- `MODIFY_PROTECTIVE` position or pending order;
- `CANCEL_PENDING`;
- `CLOSE`;
- `PARTIAL_CLOSE`;
- `BREAK_EVEN`;
- `TRAILING`.

Selecting full scope does not bypass evidence. Each operation has its own capability, risk, reconciliation, rollback and audit gate. An operation remains hard-denied until its gate is independently evidenced. The first controlled runtime scope may be narrower even when the contract is full-scope; no operation is automatically enabled by declaring it in an authorization record.

## Required gate matrix

| Gate | Required evidence | Current status / blocking rule |
| --- | --- | --- |
| Runtime compile | Exact target source/configuration compiled with target MetaEditor, `0 errors, 0 warnings`, build identity and retained output | `RUNTIME_EVIDENCE_PENDING` until adapter-specific target evidence is retained |
| Demo/retained evidence | Controlled evidence for each proposed operation: preflight, acknowledgement, reconciliation, restart/timeout/unknown, side-effect snapshots | `RUNTIME_EVIDENCE_PENDING`; offline/synthetic evidence never substitutes |
| Risk policy | Versioned selected profile, FTMO/balance limits, target overrides, sizing inputs, broker constraints and current reconciliation binding | `NOT_AUTHORIZED` until bound to exact intent |
| Manual authorization | Explicit approval naming terminal-discovered account/server, canonical/broker symbols, operation scope, max exposure, policy profile/version, target overrides and time window | `NOT_AUTHORIZED` |
| Kill switch | Reachable tested control rejecting new requests | `NOT_AUTHORIZED` until retained target-runtime test |
| Rollback | Tested disable/rollback for acknowledgement, partial execution, timeout, restart, race and `EXECUTION_UNKNOWN` | `NOT_AUTHORIZED` until retained result |
| Audit | Durable redacted chain linking intent, policy, target overrides, authorization, request, reconciliation, kill-switch/rollback and final disposition | `NOT_AUTHORIZED` until complete |

All gates are mandatory.

## Time and authorization window

Operators enter authorization window times in GMT+7. The system converts and stores them as UTC, compares only UTC, and displays both local GMT+7 and UTC for review. A window expires on end time, identity/config/policy revision change, kill-switch activation, stale reconciliation, or unknown state.

## State rules

- `PAPER_EXCLUDED_PERMANENTLY` is permanent.
- `IMPLEMENTED_DISABLED_BY_DEFAULT` describes adapter availability, not authorization.
- `RUNTIME_EVIDENCE_PENDING` describes missing/non-retained runtime evidence.
- `NOT_AUTHORIZED` is required whenever any gate is open, stale, ambiguous, or unbound.
- `AUTHORIZED_CONTROLLED_LIVE` may be recorded only after manual review closes every applicable gate and the UTC authorization window is active.
- `EXECUTION_UNKNOWN` blocks new entries and requires fresh broker reconciliation; it is never cleared by retrying the same intent.

## Explicit non-claims

This design does not claim that live trading is ready, authorized, safe, or active. No Paper ledger is implemented. Existing offline, compile, tester or bounded observer evidence cannot be promoted to live evidence without the gate matrix.
