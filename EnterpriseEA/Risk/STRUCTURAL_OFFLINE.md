# Structural SL/TP price proposal (offline)

`StructuralLevels.mqh` implements only the price geometry from Appendix B RISK-01/RISK-02 of the v1.1 specification. The setup must first supply an evidenced entry reference, thesis invalidation price and structural target. The caller also supplies a positive stop buffer in price units and a tick size from a validated instrument profile.

For BUY, the proposed SL is the invalidation minus the buffer, rounded down to a tick, and TP is the structural target rounded down. For SELL, SL is invalidation plus the buffer, rounded up, and TP is target rounded up. This conservative rounding keeps the stop outside invalidation and avoids claiming a better target than the selected structural price. Invalid direction, nonpositive inputs, wrong price ordering or levels collapsed by rounding return a reason code.

`PROPOSED_LEVELS_ONLY` means price geometry passed. It never means the trade is eligible. The next risk steps must check current bid/ask and spread, stop/freeze distances, net reward/risk after fees and slippage, target space, broker loss per lot, account policy headroom, portfolio exposure and margin. No volume or order intent is produced here. The module is not included by the EA shell; it has no MT5 compilation or runtime proof.

`Tests/Fixtures/structural-levels-v0.1.0.json` provides synthetic BUY/SELL and rejection examples. `Tests/structural_levels_tests.py` computes their expected outcomes with decimal arithmetic as an offline design check. These tests do not execute the MQL5 module.
