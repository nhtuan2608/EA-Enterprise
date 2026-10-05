"""G23: convert the long-history MT5 exports (raw, read-only) into the research bar format.

  python convert_raw.py [--raw "D:\\Work\\Private\\AI APP\\Trading-with-AI\\input\\raw"]

Writes research/long/data/bars_<SYMBOL>_<TF>.csv, tickvol_<SYMBOL>_H1.csv (time = server wall clock as epoch seconds,
like the EA export) and bars_meta.json, and prints the bar count per year. A zero spread (early
years of some exports) is replaced by that file's median non-zero spread so costs are not
understated.
"""
from __future__ import annotations

import calendar
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = Path(r"D:\Work\Private\AI APP\Trading-with-AI\input\raw")
OUT = HERE / "data"
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
TIMEFRAMES = ["M5", "H1", "H4"]
# Point and digits as on the EA's broker (research/bars_meta.json of 05/10/2026).
START = {"XAUUSD": 1519862400, "BTCUSD": 1514764800}     # 2018-03-01, 2018-01-01 (dense data from here)
SPEC = {"EURUSD": (0.00001, 5), "GBPUSD": (0.00001, 5), "XAUUSD": (0.01, 2), "BTCUSD": (0.01, 2), "USDJPY": (0.001, 3)}


def parse_line(line: str):
    parts = line.rstrip("\r\n").split("\t")
    if len(parts) < 9 or not parts[0][:1].isdigit():
        return None
    y, mo, d = (int(x) for x in parts[0].split("."))
    hh, mm, ss = (int(x) for x in parts[1].split(":"))
    t = calendar.timegm((y, mo, d, hh, mm, ss, 0, 0, 0))
    o, h, lo, c = (float(x) for x in parts[2:6])
    return t, o, h, lo, c, int(parts[8])


def convert(src: Path, dst: Path, start: int = 0) -> Counter:
    rows = [r for r in (parse_line(l) for l in src.read_text(encoding="utf-8", errors="replace").splitlines())
            if r and r[0] >= start]
    rows.sort()
    rows = [r for i, r in enumerate(rows) if i == 0 or r[0] != rows[i - 1][0]]   # one bar per time
    recent = [r[5] for r in rows if r[5] > 0 and r[0] >= 1704067200]          # 2024-01-01 onwards
    nonzero = recent or [r[5] for r in rows if r[5] > 0]
    fill = int(statistics.median(nonzero)) if nonzero else 0
    years = Counter()
    with dst.open("w", encoding="utf-8", newline="") as fh:
        fh.write("time,open,high,low,close,spread\n")
        last = None
        for t, o, h, lo, c, sp in rows:
            if t == last:
                continue
            last = t
            fh.write(f"{t},{o},{h},{lo},{c},{max(sp, fill)}\n")
            years[time_year(t)] += 1
    return years


def convert_tickvol(src: Path, dst: Path, start: int = 0) -> int:
    """G28: tick volume (MT5 <TICKVOL>) of each bar, kept apart from the bar files: time,tickvol."""
    seen, n = set(), 0
    with dst.open("w", encoding="utf-8", newline="") as fh:
        fh.write("time,tickvol" + chr(10))
        for line in sorted(src.read_text(encoding="utf-8", errors="replace").splitlines()):
            r = parse_line(line)
            if not r or r[0] < start or r[0] in seen:
                continue
            seen.add(r[0])
            fh.write(f"{r[0]},{int(line.split(chr(9))[6])}" + chr(10))
            n += 1
    return n


def time_year(t: int) -> int:
    return int(__import__("time").gmtime(t).tm_year)


def main(argv: list[str]) -> None:
    if "--tickvol" in argv:                 # only the tick volume files (G28)
        raw = Path(argv[argv.index("--raw") + 1]) if "--raw" in argv else RAW
        for sym in SYMBOLS:
            files = sorted((raw / sym).glob(f"{sym}_H1_*.csv"))
            if files:
                print(f"{sym} H1 tickvol: {convert_tickvol(files[0], OUT / f'tickvol_{sym}_H1.csv', START.get(sym, 0))}")
        return
    raw = Path(argv[argv.index("--raw") + 1]) if "--raw" in argv else RAW
    OUT.mkdir(parents=True, exist_ok=True)
    last_time = 0
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            files = sorted((raw / sym).glob(f"{sym}_{tf}_*.csv"))
            if not files:
                print(f"{sym} {tf}: none")
                continue
            dst = OUT / f"bars_{sym}_{tf}.csv"
            years = convert(files[0], dst, START.get(sym, 0))
            print(f"{sym} {tf}: " + " ".join(f"{y}:{n}" for y, n in sorted(years.items())))
            with dst.open(encoding="utf-8") as fh:
                *_, tail = fh
            last_time = max(last_time, int(tail.split(",")[0]))
    for sym in SYMBOLS:
        files = sorted((raw / sym).glob(f"{sym}_H1_*.csv"))
        if files:
            print(f"{sym} H1 tickvol: {convert_tickvol(files[0], OUT / f'tickvol_{sym}_H1.csv', START.get(sym, 0))}")
    # G26 step 3: intermarket context (H1 only), same conversion; the folders use other file prefixes.
    for name, folder, prefix in (("DXY", "DXY", "USDX."), ("US10Y", "US10Y", "USNote10Y")):
        files = sorted((raw / folder).glob(f"{prefix}_H1_*.csv"))
        if files:
            years = convert(files[0], OUT / f"bars_{name}_H1.csv")
            print(f"{name} H1: " + " ".join(f"{y}:{n}" for y, n in sorted(years.items())))
    # Server offset at the end of the data (October: US summer time, broker UTC+3).
    meta = {"from_utc": 1262304000, "swing_from_utc": 1262304000, "exported_at_utc": last_time - 10800,
            "server_offset_now": 10800, "source": str(raw),
            "symbols": [{"symbol": s, "broker": s, "point": SPEC[s][0], "digits": SPEC[s][1]} for s in SYMBOLS]}
    (OUT / "bars_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
