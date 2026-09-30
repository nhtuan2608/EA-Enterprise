# Account-wide risk ledger prototype (offline)

`AccountRiskLedger.mqh` is a pure reducer for caller-supplied, already reconciled account snapshots. It does not read MT5 positions/orders/deals and does not send, amend, or close orders. It is not included in the EA shell and does not prove real account reconciliation.

## Tracked amounts

- `initial_risk_money`: sum of original risk captured at entry for currently open positions. It remains fixed through SL changes.
- `projected_loss_to_sl_money`: original intent risk stored for each open position plus projected risk for unfilled working-order quantities.
- `remaining_loss_to_sl_money`: caller-calculated current loss to current SL for open positions plus current projected risk for remaining working-order quantities.
- Floating P/L is supplied net of costs; locked profit is tracked separately. Policy floor headroom is carried from a version/currency-matched policy snapshot, and the ledger subtracts current remaining risk to produce `floor_headroom_after_ledger_risk_money`.

A partial fill appears as a position row plus a residual `PARTIAL` working-order row. An SL change updates remaining loss while preserving initial and original projected risk. Each open row must carry `risk_lineage_valid=true`, a caller attestation that entry and intent values were retained. The reducer does not keep per-position history and cannot independently detect a caller changing those values while continuing to attest them as valid. A close removes the position from the next complete snapshot. EA, MANUAL and OTHER_EA rows all contribute to the same totals. HEDGING permits multiple position tickets per symbol; NETTING rejects duplicate open rows for a broker symbol because the caller should provide the broker's single net position representation.

## Snapshot state

Each update must have fresh, unique event/snapshot IDs and monotonic event sequence/time, plus a nonempty `content_fingerprint` over all material snapshot values and rows. The fingerprint is caller-supplied and caller-attested; this prototype does not calculate it cryptographically or prove it covers every field. Repeated IDs/sequence with a changed fingerprint fail closed. Position, working-order and deal sources must be complete and reconciled account-wide. Manual and other-EA activity, account mode, costs, commission/swap, and deposit/withdrawal cash flows must be explicitly covered. Policy headroom must match the same config version and account currency. Deal rows must have unique IDs and ascending sequence through the declared watermark; completeness through that watermark remains a caller attestation and is not proven by the reducer.

An identical repeated snapshot is ignored idempotently only while it remains fresh and the ledger is reconciled. Replaying the last good snapshot after a later error does not clear unknown state. Reused IDs with different content, stale/missing sources, out-of-order snapshots, identity/mode changes, invalid rows, or missing policy evidence put the ledger in `POLICY_DATA_UNKNOWN` and block new entries while retaining the last good totals and the `protect_existing_positions` safety flag. A later newer complete snapshot can reconcile again. A valid snapshot with zero or negative post-ledger floor headroom remains `RECONCILED` but blocks new entries.

The ledger validates assertions and arithmetic; it cannot prove the caller actually included all account activity or correctly normalized netting, conversions, open costs, locked profit, or current SL loss. A production reconciler must compare terminal positions, active orders and deals with history at startup/reconnect and before use. The flag protecting existing positions communicates the required safety posture; it does not implement position protection.

`Tests/Fixtures/account-risk-ledger-v0.1.0.json` and `Tests/account_risk_ledger_oracle.py` exercise partial fills, SL modification, close, duplicate/out-of-order snapshots, external origins, hedging/netting, missing evidence and floor exhaustion using synthetic values. These are design checks only; MQL5 compilation and account/broker behavior remain unverified.
