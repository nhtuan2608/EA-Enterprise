# Corrective runtime wiring task

Repository/worktree: D:\Work\Private\Trading\EA-Enterprise\.worktrees\retained-runtime-correction

## Root cause findings

The merged main branch has telemetry/storage fields but does not fully wire lifecycle behavior:
- `EEA_RuntimeDefaults` initializes status fields, but `EEA_ObserverRuntimeRefresh` does not preserve/update all telemetry around `EEA_RuntimeValidate` and failure paths.
- `EEA_RuntimeStoreWriteSymbolSelection` exists but startup does not load compatible persisted canonical selection; apply/startup behavior must never trust stored broker mappings.
- `EEA_ObserverRuntimeMarkStale` currently has signature `(ctx, reason)`, does not increment callback/invalidation counters coherently or emit `BROKER_TRANSACTION_OBSERVED`; `EnterpriseEA.mq5` calls this handler without audit.
- `OnTimer` counts ticks only if current code already does; verify and complete reentrancy/pending semantics.
- Apply selection must write selection atomically only after successful fresh reconciliation and rollback arrays/revision on failure.

## Required scope

Modify only these files plus a report:
- `EnterpriseEA/Runtime/RuntimeEvidence.mqh`
- `EnterpriseEA/Runtime/ObserverRuntime.mqh`
- `EnterpriseEA/Storage/RuntimeEvidenceStore.mqh`
- `EnterpriseEA/EnterpriseEA.mq5`
- `EnterpriseEA/Tests/runtime_evidence_tests.py`
- Create `EnterpriseEA/task-6-report.md`

Do not use or apply the stashed local patch; implement cleanly against current HEAD.

## Required behavior

1. Add tests first and run a correct RED. Tests must assert source wiring for every status field, `EEA_RuntimeDefaults` assignments, `EEA_RuntimeStoreWriteSymbolSelection` calls from startup/success/apply, `refresh_in_progress`, `refresh_attempt_count`, `refresh_sequence`, `refresh_generation`, duration/max duration, success/failure/consecutive counters, timer tick/time, pending refresh, callback/invalidation counters, audit event, and `OnTradeTransaction` audit signature.
2. `EEA_RuntimeDefaults` initializes every field deterministically; selection revision starts at 0 or 1 consistently with tests/spec.
3. Runtime init establishes unique instance identity, starts blocked/stale, discovers canonical symbols, checks persisted selection compatibility, and always fresh reconciles. Stored broker mappings are never authority. If full array parse is unsafe, use a strict narrow parser that extracts only canonical symbols and validates capacity/identity; otherwise CSV fallback.
4. Refresh has reentrancy guard; increments attempt/sequence/generation once; preserves telemetry while assigning validation status; updates broker/checkpoint timestamps and duration/max duration; increments success/failure and consecutive failure counters; sets `refresh_in_progress=false` on every exit; writes account/symbol/reconciliation/selection/status snapshots in order; status write must include populated telemetry.
5. `EEA_ObserverRuntimeMarkStale(ctx, reason, audit)` increments callback count for every callback; only fresh-to-stale increments invalidation generation, sets pending, and appends exactly one `BROKER_TRANSACTION_OBSERVED` audit event; it never reads or mutates broker.
6. `OnTimer` increments timer count/timestamp; if in-progress sets pending and returns; otherwise refreshes stale/pending/due; no backlog.
7. Apply selection discovers temporary broker mapping, increments revision, refreshes/persists; on failure restores canonical/broker/count/revision and leaves prior committed selection active.
8. Preserve canonical-only inputs, `InpBrokerSymbols` absent, empty OnTick, observer-only refusal, `EEA_StateCanAllowEntry=false`, no Paper/live/order APIs.

## Verification

Run:
- `python -m unittest discover -s Tests -p '*tests.py' -v`
- compile `EnterpriseEA.mq5` with MetaEditor build 6230, require `Result: 0 errors, 0 warnings`
- static scan all `.mq5/.mqh` for `OrderSend|OrderSendAsync|CTrade|OrderDelete|PositionClose|PositionModify|OrderModify`
- remove generated `.ex5`, logs, `Tests/__pycache__` before commit

Write report at `EnterpriseEA/task-6-report.md` with RED/GREEN/compile evidence and explicitly state retained terminal GUI/soak/external activity remain pending unless actually observed. Commit message: `fix: wire retained observer runtime lifecycle`. Return actual new SHA, not a previous SHA.
