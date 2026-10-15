"""G106 shadow forward: record the virtual trades of the simplified context + BOX rule on new data (no orders).

  python g106_shadow.py            -> rebuilds every virtual trade from SHADOW_START on fresh MT5 bars

Read-only: the running terminal's XAUUSD bars (MetaTrader5 copy_rates_from_pos); nothing is sent to the terminal.
The result is deterministic, so the script can run at any time (daily or weekly) and always gives the full book:
  research/forward/g106_shadow_trades.csv   one row per virtual trade (closed and open), every timeframe pair
  research/forward/g106_shadow_summary.md   per timeframe and direction: trades, R/trade, total R, open trades
Rules: g106_ctx_box.py (entry when the context switches on, BOX hold on the higher timeframe, no target).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import g106_ctx_box as g

SHADOW_START = pd.Timestamp("2026-10-12")          # server time; trades opened from here on are forward
BROKER = "XAUUSD-VIP"
TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
OUT = Path(__file__).resolve().parents[1] / "forward"
BARS = {"M5": 30000, "M15": 20000, "M30": 20000, "H1": 20000}


def fetch(tf: str) -> pd.DataFrame:
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERMINAL):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        mt5.symbol_select(BROKER, True)
        r = mt5.copy_rates_from_pos(BROKER, getattr(mt5, "TIMEFRAME_" + tf), 1, BARS[tf])   # closed bars only
    finally:
        mt5.shutdown()
    if r is None or len(r) == 0:
        raise RuntimeError(f"no {tf} bars")
    df = pd.DataFrame(r)
    df = df.rename(columns={"tick_volume": "tickvol"})[["time", "open", "high", "low", "close", "tickvol", "spread"]]
    df["ts"] = pd.to_datetime(df["time"], unit="s")
    return df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, lines = [], []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for tf, (_, hi_rule) in g.PAIRS.items():
        m = g.prepare(fetch(tf), hi_rule)
        S = g.Sim(m)
        for d in (-1, 1):
            ctx = g.context(m, d)
            sw = ctx & ~np.concatenate([[False], ctx[:-1]])
            sw &= (m["ts"] >= SHADOW_START).to_numpy()
            t = g.book(S, m, d, sw)
            for r in t.itertuples():
                rows.append(dict(tf=tf, dir="SELL" if d == -1 else "BUY", signal_time=r.t, entry=round(r.entry, 2),
                                 status="open" if r.why == "open" else "closed", exit_reason=r.why,
                                 exit_time=r.exit_t if r.why != "open" else pd.NaT, r=round(r.r, 2),
                                 days=round(r.days, 1)))
        last = m["ts"].iat[-1]
        lines.append(f"- {tf}: bars up to {last:%Y-%m-%d %H:%M} (server)")
    t = pd.DataFrame(rows, columns=["tf", "dir", "signal_time", "entry", "status", "exit_reason", "exit_time", "r", "days"])
    t.to_csv(OUT / "g106_shadow_trades.csv", index=False)
    md = [f"# G106 shadow forward (virtual trades, no orders)", "",
          f"Updated {now}. Forward from {SHADOW_START:%Y-%m-%d} (server time). Rule: context switch on + BOX hold.", ""]
    md += lines + ["", "| TF | Dir | Closed | R/trade (closed) | Total R (closed) | Open | Open R now |",
                   "|---|---|---|---|---|---|---|"]
    for tf in g.PAIRS:
        for dname in ("BUY", "SELL"):
            x = t[(t["tf"] == tf) & (t["dir"] == dname)]
            c, o = x[x["status"] == "closed"], x[x["status"] == "open"]
            md.append(f"| {tf} | {dname} | {len(c)} | {c['r'].mean() if len(c) else float('nan'):+.2f} | "
                      f"{c['r'].sum():+.1f} | {len(o)} | {o['r'].sum():+.1f} |")
    (OUT / "g106_shadow_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
