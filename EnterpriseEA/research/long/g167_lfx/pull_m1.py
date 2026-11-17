import MetaTrader5 as mt5, pandas as pd
from datetime import datetime, timezone
assert mt5.initialize(), mt5.last_error()
for s in ("XAUUSD-VIP", "XAGUSD-VIP", "USOUSD-VIP"):
    parts = []
    for m in range(5, 12):
        a = datetime(2026, m, 1, tzinfo=timezone.utc) if m > 5 else datetime(2026, 5, 25, tzinfo=timezone.utc)
        b = datetime(2026, m + 1, 1, tzinfo=timezone.utc) if m < 11 else datetime(2026, 11, 18, tzinfo=timezone.utc)
        r = mt5.copy_rates_range(s, mt5.TIMEFRAME_M1, a, b)
        if r is None or len(r) == 0:
            print(s, m, "none", mt5.last_error()); continue
        parts.append(pd.DataFrame(r))
    if parts:
        d = pd.concat(parts).drop_duplicates("time").sort_values("time"); d.to_csv(f"{s}_M1.csv", index=False)
        print(s, len(d), pd.to_datetime(d.time.iloc[0], unit="s"), pd.to_datetime(d.time.iloc[-1], unit="s"))
mt5.shutdown()
