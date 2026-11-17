import MetaTrader5 as mt5, pandas as pd
from datetime import datetime, timezone
assert mt5.initialize(), mt5.last_error()
syms = [s.name for s in mt5.symbols_get() if any(k in s.name for k in ("XAUUSD", "XAGUSD", "USO", "WTI", "OIL"))]
print(syms)
for s in syms:
    mt5.symbol_select(s, True)
    for tf, lab in ((mt5.TIMEFRAME_M1, "M1"), (mt5.TIMEFRAME_M5, "M5")):
        r = mt5.copy_rates_range(s, tf, datetime(2026, 5, 25, tzinfo=timezone.utc), datetime(2026, 11, 18, tzinfo=timezone.utc))
        if r is None or len(r) == 0:
            print(s, lab, "none", mt5.last_error()); continue
        d = pd.DataFrame(r); d.to_csv(f"{s}_{lab}.csv", index=False)
        print(s, lab, len(d), pd.to_datetime(d.time.iloc[0], unit="s"), pd.to_datetime(d.time.iloc[-1], unit="s"))
t = mt5.symbol_info_tick("XAUUSD-VIP"); print("server-utc h", round((t.time - datetime.now(timezone.utc).timestamp())/3600))
mt5.shutdown()
