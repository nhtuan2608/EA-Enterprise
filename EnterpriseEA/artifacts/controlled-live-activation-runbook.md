# Controlled-live activation runbook

This runbook is for the paperless market-only route. It does not create a virtual or Paper execution path.

1. Run tools/deploy_target.ps1 -SourceRoot <workspace>\EnterpriseEA -TargetRoot <target> -RequireBinaryChanged and retain both the MetaEditor result (0 errors, 0 warnings) and the changed EX5 hash/timestamp. If the binary does not change, detach/reload the EA and retry before validating the terminal and panel. Keep InpObserverOnly=true, InpExecutionEnabled=false, and InpLiveTradeArmed=false while validating the terminal and panel.
2. Run tools/verify_live_readiness.ps1 -DataRoot <data-root>\current -TargetRoot <target>. Treat NOT_READY as a hard stop; READY_FOR_MANUAL_REVIEW still requires human approval of the exact account, symbol scope, policy, limits, kill switch and rollback evidence.
2. Validate the live terminal account/server, broker symbol mapping, material symbol specifications, account-wide positions/orders/deals reconciliation, and the selected policy. Do not type raw login or account-holder identity into artifacts.
3. Run the applicable controlled demo/retained operation protocol, including acknowledgement, fresh reconciliation, restart, timeout/unknown, kill-switch, rollback, and audit-tail checks. Synthetic tests do not close these gates.
4. Prepare an exact-identity authorization document from `live-authorization-template.json`. Set every gate to `true` only after the corresponding retained evidence is reviewed; bind `candidate_id`, `intent_id`, account fingerprint, server, broker symbol, config version, and expiry to the one intended operation.
5. Prepare a durable controller document for scope `MARKET_ENTRY` with `kill_active=false`, a monotonic revision, operator reference, and a bounded UTC window. Keep the controller kill active until the final review.
6. Configure the explicit live inputs: `InpObserverOnly=false`, `InpExecutionEnabled=true`, `InpLiveTradeArmed=true`, a non-empty approved strategy config, and complete risk inputs (capital/reset/high-water/risk cap/target/spread/margin parameters). Zero defaults are intentionally invalid.
7. Attach the EA to the live terminal. The runtime must remain blocked if any identity, evidence, policy, controller, authorization, risk release, persistence, or reconciliation check fails. After an acknowledgement, `EXECUTION_UNKNOWN` is a restart barrier; it is never retried silently.
8. After the bounded market-only operation, retain pre/post snapshots, execution intent, risk decision, result, reconciliation, audit, and operator disposition. Revoke the controller and disarm the EA after the test window.

The current repository state remains `NOT_AUTHORIZED`; this document is procedural evidence guidance, not approval.

## Attach error 32767

`INIT_PARAMETERS_INCORRECT (32767)` is emitted by the EA's `OnInit` validation.
For observer validation, reset the inputs and keep
`InpObserverOnly=true`, `InpExecutionEnabled=false`,
`InpLiveTradeArmed=false`, and `InpStrategyRuntimeEnabled=false`. If a live
profile is intentionally selected, all three live-mode conditions must be
explicitly valid; otherwise initialization is rejected fail-closed. The latest
source logs a reason beginning with `INIT_PARAMETERS_INCORRECT:` for each
validation branch. Compile/deploy the latest EX5 before relying on that
diagnostic.
