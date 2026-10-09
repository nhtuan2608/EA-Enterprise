"""G67 data: M15 bars with tick volume, MT5 only.

The raw MT5 export (input/raw/<SYMBOL>/<SYMBOL>_M15_*.csv, broker server time, tab separated) is
extended with the bars the running terminal holds after the export ended (read-only, MetaTrader5).
Output: data/m15v/<SYMBOL>.csv with time (server epoch), open, high, low, close, tickvol, spread.

  python g67_data.py
"""
from __future__ import annotations

import csv
import glob
from datetime import datetime, timezone
from pathlib import Path

RAW = Path(r"D:\Work\Private\AI APP\Trading-with-AI\input\raw")
OUT = Path(__file__).resolve().parent / "data" / "m15v"
BROKER = {"XAUUSD": "XAUUSD-VIP", "XAGUSD": "XAGUSD-VIP", "USDJPY": "USDJPY-VIP", "EURUSD": "EURUSD-VIP",
          "GBPUSD": "GBPUSD-VIP", "BTCUSD": "BTCUSD"}


def raw_rows(symbol: str) -> list[tuple]:
    files = sorted(glob.glob(str(RAW / symbol / f"{symbol}_M15_*.csv")))
    if not files:
        return []
    rows = []
    with open(files[-1], newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)
        for r in reader:
            t = datetime.strptime(r[0] + " " + r[1], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
            rows.append((int(t.timestamp()), float(r[2]), float(r[3]), float(r[4]), float(r[5]), int(r[6]), int(r[8])))
    return rows


def terminal_rows(symbol: str, after: int) -> list[tuple]:
    import MetaTrader5 as mt5
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        raise RuntimeError(mt5.last_error())
    try:
        r = mt5.copy_rates_from_pos(BROKER[symbol], mt5.TIMEFRAME_M15, 1, 60000)
    finally:
        mt5.shutdown()
    if r is None:
        return []
    return [(int(x["time"]), float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"]),
             int(x["tick_volume"]), int(x["spread"])) for x in r if int(x["time"]) > after]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for s in BROKER:
        raw = raw_rows(s)
        tail = terminal_rows(s, raw[-1][0] if raw else 0)
        rows = raw + tail
        if not rows:
            print(s, "no data")
            continue
        with open(OUT / f"{s}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "open", "high", "low", "close", "tickvol", "spread"])
            w.writerows(rows)
        d = lambda t: datetime.fromtimestamp(t, timezone.utc).date()
        print(f"{s}: raw {len(raw)} + terminal {len(tail)} bars, {d(rows[0][0])} .. {d(rows[-1][0])}")


if __name__ == "__main__":
    main()
