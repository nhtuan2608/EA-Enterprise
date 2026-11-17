import MetaTrader5 as mt5, pandas as pd
from datetime import datetime, timezone
assert mt5.initialize()
names = [s.name for s in mt5.symbols_get() if s.name.startswith(("BTCUSD", "EURUSD"))]
print(names)
for s in ("BTCUSD-VIP", "EURUSD-VIP"):
    if s not in names:
        cand = [n for n in names if n.startswith(s[:6])]
        s = cand[0] if cand else s
    mt5.symbol_select(s, True)
    for tf, lab, n in ((mt5.TIMEFRAME_M5, "M5", 60000), (mt5.TIMEFRAME_M15, "M15", 20000), (mt5.TIMEFRAME_H1, "H1", 6000), (mt5.TIMEFRAME_H4, "H4", 2000), (mt5.TIMEFRAME_D1, "D1", 700)):
        r = mt5.copy_rates_from_pos(s, tf, 0, n)
        if r is None: print(s, lab, mt5.last_error()); continue
        pd.DataFrame(r).to_csv(f"{s[:6]}-VIP_{lab}.csv" if not s.endswith("-VIP") else f"{s}_{lab}.csv", index=False)
        print(s, lab, len(r), pd.to_datetime(r[0]["time"], unit="s"))
    parts = []
    for m in range(8, 12):
        r = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1, datetime(2026, m, 1, tzinfo=timezone.utc), datetime(2026, m + 1, 1, tzinfo=timezone.utc) if m < 11 else datetime(2026, 11, 18, tzinfo=timezone.utc))
        if r is not None and len(r): parts.append(pd.DataFrame(r))
    if parts:
        d = pd.concat(parts).drop_duplicates("time").sort_values("time")
        d.to_csv(f"{s[:6]}-VIP_M1.csv", index=False); print(s, "M1", len(d), pd.to_datetime(d.time.iloc[0], unit="s"))
mt5.shutdown()
