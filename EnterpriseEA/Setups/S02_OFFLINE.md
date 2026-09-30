# S02 Break Retest offline prototype

`BreakRetest.mqh` is a pure, isolated closed-bar state machine. It is not included by `EnterpriseEA.mq5` and has no timer/tick, broker, symbol lookup, order, risk, news, AI, or UI calls. Keeping it isolated avoids claiming compile safety while MetaEditor is unavailable.

## Input and state sequence

The caller initializes one engine for one canonical symbol and timeframe, then passes only completed OHLC bars, ATR, and one externally selected key level. The key level and ATR at break are pinned for the candidate. A live adapter must use the previous completed bar (MT5 series index 1), validate its symbol mapping first, and avoid calling this module with an unfinished candle.

```text
IDLE -> DETECTED -> ARMED -> RETESTING -> TRIGGERED -> EXPIRED
             \         \          \-> INVALIDATED
              \-> INVALIDATED / EXPIRED
```

- `DETECTED`: a completed bar closes beyond the key by the configured ATR buffer.
- `ARMED`: a later close confirms acceptance beyond the key.
- `RETESTING`: a later bar overlaps the retest band and does not close through invalidation.
- `TRIGGERED`: a subsequent bar closes on the correct side with directional body and progress beyond the retest close.
- `INVALIDATED`: the close crosses the candidate's invalidation price or the level is lost before retest.
- `EXPIRED`: acceptance, retest, reaction, or candidate TTL window ends.

This prototype ends at `TRIGGERED`. It does not check target, space, cost, opportunity filters, risk, or account policy. It never yields `ELIGIBLE`, `RISK_APPROVED`, or `ORDER_INTENT`.

## Research seed settings

`EEA_S02ResearchSeedConfig` uses 0.10 ATR break buffer, 0.00 ATR acceptance buffer, 0.15 ATR retest tolerance, 0.10 ATR invalidation buffer, 0.05 ATR hold buffer, windows of 2/3/2 bars, and a 3-bar triggered candidate TTL. These are reproducible test seeds only. They have not been optimized, approved, or connected to an instrument profile.

Closed bars with the same timestamp produce `DUPLICATE_CLOSED_BAR`; older bars produce `OUT_OF_ORDER_CLOSED_BAR`. Neither advances state. Candidate IDs include canonical symbol, timeframe, config version, and break-bar timestamp. Engine identity and config version are fixed at initialization; changing them requires a fresh engine.

## Offline evidence

`Tests/Fixtures/s02-observer-v0.1.0.json` defines all synthetic bars and expected transitions. `Tests/s02_oracle.py` is a standard-library design oracle, not the EA engine. The suite checks long and short sequences, acceptance and retest expiry, failed hold, duplicate bars, identity, and restart parity by cloning an oracle checkpoint. It does not execute or compile the MQL5 module. MetaEditor compilation and comparison of MQL outputs with these same fixtures remain required on an MT5-enabled machine.
