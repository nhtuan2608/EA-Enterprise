"""G138 on the PC, steps 1a and 1b (read-only checks of the research bars and of the terminal's D1 bars).

1a  research/long/data/{m30v,m15v,h1v}/XAUUSD.csv: bars per weekday of the server time, server days per week, Sunday bars;
    the server-UTC offset g67_dmi_ema.load assumes (UTC+2, UTC+3 while US DST: New York close at server midnight) checked
    against NFP: 08:30 New York = 15:30 server under that rule all year, so on first Fridays the widest bar of 13:00-18:00
    server should start at 15:30 (M15/M30) or 15:00 (H1).
1b  400 D1 bars of XAUUSD-VIP from the running terminal (MetaTrader5 copy_rates_from_pos, read only): weekdays, Sunday bars.

Usage: g138_pc_checks.py <data dir> <out.json> [--no-terminal]
"""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

DAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]


def weekday_profile(df):
    t = pd.to_datetime(df["time"], unit="s", utc=True)          # server clock stored as epoch seconds
    wd = Counter(t.dt.weekday)
    days = t.dt.floor("D")
    weeks = (t - pd.to_timedelta(t.dt.weekday, unit="D")).dt.floor("D")
    per_week = days.groupby(weeks).nunique()
    full = per_week.iloc[1:-1]                                    # first and last week may be partial
    by_year = {}
    for y, grp in per_week.groupby(per_week.index.year):
        by_year[int(y)] = round(float(grp.mean()), 2)
    sun = t[t.dt.weekday == 6]
    return {"bars": int(len(df)), "first": str(t.iloc[0]), "last": str(t.iloc[-1]),
            "bars_per_weekday": {DAYS[k]: int(wd.get(k, 0)) for k in range(7)},
            "server_days_per_week_mean": round(float(full.mean()), 3),
            "weeks_with_6_or_more_days": int((full >= 6).sum()), "weeks": int(len(full)),
            "server_days_per_week_by_year": by_year,
            "sunday_bars": int(len(sun)), "sunday_examples": [str(x) for x in sun.head(5)]}


def first_fridays(y0, y1):
    out = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            d = datetime(y, m, 1, tzinfo=timezone.utc)
            out.append(d.replace(day=1 + (4 - d.weekday()) % 7))
    return out


def nfp_check(df, bar_sec):
    """Widest bar between 13:00 and 18:00 server on first Fridays; under the g67 offset rule NFP is 15:30 server."""
    t = pd.to_datetime(df["time"], unit="s", utc=True)
    rng = (df["high"] - df["low"]).to_numpy()
    starts = Counter()
    n = 0
    for fr in first_fridays(int(t.iloc[0].year), int(t.iloc[-1].year)):
        a, z = pd.Timestamp(fr) + pd.Timedelta(hours=13), pd.Timestamp(fr) + pd.Timedelta(hours=18)
        idx = np.nonzero(((t >= a) & (t < z)).to_numpy())[0]
        if len(idx) < 3:
            continue
        k = idx[int(np.argmax(rng[idx]))]
        starts[t.iloc[k].strftime("%H:%M")] += 1
        n += 1
    want = "15:30" if bar_sec <= 1800 else "15:00"
    return {"first_fridays": n, "widest_bar_start_server": dict(starts.most_common(6)),
            "share_at_expected": round(starts.get(want, 0) / max(n, 1), 3), "expected_start": want}


def terminal_d1(symbol="XAUUSD-VIP", n=400):
    import MetaTrader5 as mt5
    if not mt5.initialize():
        return {"error": f"initialize failed {mt5.last_error()}"}
    try:
        r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, n)
        if r is None:
            return {"error": f"copy_rates_from_pos failed {mt5.last_error()}"}
        t = pd.to_datetime(r["time"], unit="s", utc=True)
        wd = Counter(t.weekday)
        weeks = (t - pd.to_timedelta(t.weekday, unit="D")).floor("D")
        per_week = pd.Series(1, index=t).groupby(weeks).sum()
        return {"symbol": symbol, "bars": int(len(r)), "first": str(t[0]), "last": str(t[-1]),
                "bars_per_weekday": {DAYS[k]: int(wd.get(k, 0)) for k in range(7)},
                "d1_bars_per_week_mean": round(float(per_week.iloc[1:-1].mean()), 3),
                "sunday_bars": [str(x) for x in t[t.weekday == 6]][:10],
                "server": mt5.account_info().server if mt5.account_info() else ""}
    finally:
        mt5.shutdown()


def main():
    root = Path(sys.argv[1])
    out = {"offset_rule": "g67_dmi_ema.load: utc = server - (3 h if us_dst(server - 2 h) else 2 h)"}
    for tf, sec in (("m30v", 1800), ("m15v", 900), ("h1v", 3600)):
        df = pd.read_csv(root / tf / "XAUUSD.csv")
        out[tf] = weekday_profile(df)
        out[tf]["nfp"] = nfp_check(df[df["time"] >= int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())], sec)
        print(tf, out[tf]["bars_per_weekday"], out[tf]["server_days_per_week_mean"], out[tf]["nfp"], flush=True)
    if "--no-terminal" not in sys.argv:
        out["terminal_d1"] = terminal_d1()
        print("terminal D1", out["terminal_d1"], flush=True)
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
