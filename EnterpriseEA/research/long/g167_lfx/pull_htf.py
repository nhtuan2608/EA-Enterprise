import MetaTrader5 as mt5, pandas as pd
assert mt5.initialize()
for s in ("XAUUSD-VIP", "XAGUSD-VIP", "USOUSD-VIP"):
    for tf, lab, n in ((mt5.TIMEFRAME_H1, "H1", 6000), (mt5.TIMEFRAME_H4, "H4", 2000), (mt5.TIMEFRAME_D1, "D1", 700), (mt5.TIMEFRAME_M15, "M15", 20000)):
        r = mt5.copy_rates_from_pos(s, tf, 0, n)
        pd.DataFrame(r).to_csv(f"{s}_{lab}.csv", index=False)
        print(s, lab, len(r))
mt5.shutdown()
