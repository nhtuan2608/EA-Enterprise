"""MKT01 data: M15 / M30 / H1 / H4 bars with tick volume for US indices and crypto, read from the user's MT5 terminal
(read only) into research/long/data/<tf>v/<SYMBOL>.csv. BTCUSD keeps the older exported history and appends the broker
bars after its last bar.

  python mkt01_data.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "long" / "data"
SYMBOLS = {"BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD", "SOLUSD": "SOLUSD", "XRPUSD": "XRPUSD", "LTCUSD": "LTCUSD",
           "SP500": "SP500.", "NAS100": "NAS100.", "DJ30": "DJ30."}
OLD = {"M15": "m15v/BTCUSD.csv", "M30": "bars_BTCUSD_M30.csv", "H1": "bars_BTCUSD_H1.csv", "H4": "bars_BTCUSD_H4.csv"}


def old_rows(tf):
    f = DATA / OLD[tf]
    if not f.exists():
        return []
    rows = []
    with open(f, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["time"]), r["open"], r["high"], r["low"], r["close"], int(float(r.get("tickvol") or 0)),
                         int(float(r["spread"]))))
    return rows


def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        raise RuntimeError(mt5.last_error())
    meta = {}
    try:
        codes = {"M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
        for name, broker in SYMBOLS.items():
            mt5.symbol_select(broker, True)
            info = mt5.symbol_info(broker)
            meta[name] = {"broker": broker, "point": info.point, "digits": info.digits}
            for tf, code in codes.items():
                rows = old_rows(tf) if name == "BTCUSD" else []
                tail = mt5.copy_rates_from_pos(broker, code, 1, 99000)
                tail = [] if tail is None else tail
                if rows:
                    # sanity: the broker close must match the old file where both exist
                    old = {r[0]: float(r[4]) for r in rows}
                    both = [(old[int(x["time"])], float(x["close"])) for x in tail if int(x["time"]) in old]
                    if both:
                        dev = max(abs(a / b - 1) for a, b in both)
                        meta[name][f"{tf}_overlap"] = [len(both), dev]
                last = rows[-1][0] if rows else 0
                rows += [(int(x["time"]), x["open"], x["high"], x["low"], x["close"], int(x["tick_volume"]), int(x["spread"]))
                         for x in tail if int(x["time"]) > last]
                out = DATA / f"{tf.lower()}v" / f"{name}.csv"
                out.parent.mkdir(exist_ok=True)
                with open(out, "w", newline="") as fh:
                    w = csv.writer(fh)
                    w.writerow(["time", "open", "high", "low", "close", "tickvol", "spread"])
                    w.writerows(rows)
                d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
                print(f"{name} {tf}: {len(rows)} bars {d(rows[0][0])} .. {d(rows[-1][0])}")
    finally:
        mt5.shutdown()
    (DATA / "mkt01_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
