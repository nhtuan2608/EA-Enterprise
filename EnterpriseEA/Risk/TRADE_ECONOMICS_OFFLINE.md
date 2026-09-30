# Net reward/risk check (offline)

`TradeEconomics.mqh` checks a priced candidate after structural SL/TP and final volume are known. The caller supplies account-currency cash quotes for loss at SL and net result at TP, both for the same final volume and pricing snapshot, with expected fees, swap and slippage already included. The module checks BUY/SELL price geometry, a setup/profile minimum net reward/risk, and an externally confirmed path to the target. A zero or negative net result at TP is rejected.

`ECONOMICS_ACCEPTABLE` is only a local economics result. The caller still needs policy headroom, portfolio budget, current account reconciliation, broker order constraints and any other entry gates. Missing or stale quotes, a volume mismatch or unconfirmed execution constraints return `UNKNOWN`; insufficient target space or net reward/risk return `REJECTED`. No minimum reward/risk is hardcoded for live use.

`Tests/Fixtures/trade-economics-v0.1.0.json` uses synthetic BUY/SELL amounts and a research example threshold. `Tests/trade_economics_tests.py` checks the fixture through a Python oracle; it does not execute MQL5. The module is isolated from the EA shell and has no compile or MT5 runtime proof.
