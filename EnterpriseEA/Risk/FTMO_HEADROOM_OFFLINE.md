# FTMO policy headroom prototype (offline)

`FtmoHeadroom.mqh` is an isolated pure calculation for the Phase 3 FTMO 1-Step and 2-Step policy floors. It is not included by `EnterpriseEA.mq5`, does not call terminal or broker APIs, and has no order path. The policy defaults remain `UNSELECTED`.

The output field `headroom_status` describes only local policy-floor headroom:

- `POLICY_DATA_UNKNOWN`: policy, reset snapshot, currency/version, or required 1-Step high-water evidence is missing or invalid; arithmetic overflow also fails closed.
- `BLOCK_NEW_ENTRY`: equity is at/below either floor or the safety buffer consumes all remaining headroom.
- `REDUCE_OR_WAIT`: proposed stress loss is greater than or equal to available headroom.
- `SUFFICIENT`: the proposed stress estimate fits inside the policy headroom.

`SUFFICIENT` is not entry permission. A complete entry gate still needs current account reconciliation, portfolio-wide stress, internal limits, symbol/instrument checks, valid costs and execution context. Equality at a policy floor is treated conservatively as a local block; this prototype does not assert the exact contractual broker violation behavior at equality.

The caller must provide a trusted daily reset snapshot, attest that it corresponds to 00:00 Europe/Prague including DST/reconnect handling, and version/currency match it to the active configuration. For 1-Step the caller must also provide persisted, quality-checked high-water evidence from at or before the reset. The module keeps the high-water at `max(initial capital, prior high-water, current reset balance)`, so a later lower reset balance cannot reduce the trailing floor. It does not repair missing history. For 2-Step the overall floor stays fixed at 90% of initial capital.

The equity input is current balance plus floating P/L already net of swap, commission, and fees exactly once, according to the account's accounting convention. Proposed stress loss must already be expressed in account currency and include the caller's required cost/slippage estimate. The module does not calculate position risk, convert currencies, determine reset timestamps, persist snapshots, reconcile open positions, or implement other internal limits. Daily loss rates are 3% for 1-Step and 5% for 2-Step; overall loss is 10%. All amounts in the fixture are synthetic research examples, not user or broker defaults.

Verification: `Tests/ftmo_headroom_oracle.py` is a standard-library reference oracle and `Tests/ftmo_headroom_tests.py` exercises fixed arithmetic, missing/stale evidence, reset attestation, equality, negative current balance, overflow, and module boundaries. Python tests are design checks only. MetaEditor compilation, MQL5 execution against the fixture, timezone/DST behavior, terminal persistence, and broker/account validation remain unverified.
