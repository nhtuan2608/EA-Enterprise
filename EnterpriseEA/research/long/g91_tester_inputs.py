"""G91: input files for S07Tester.mq5 so the Strategy Tester applies the live EA's News Guard and sentiment.

  python g91_tester_inputs.py

Writes into the terminal's MQL5/Files (read by the tester through #property tester_file):
  S07Tester_news.csv       HIGH events of the tracked currencies from the EA's own MT5 calendar export
                           (research/calendar/calendar_<year>.csv): time_server;currency;sector;name
  S07Tester_sentiment.csv  per closed H1 bar (server time): the gold alignment of Market/Sentiment.mqh
                           for a buy (a4, a24) and the share of related USD pairs against a buy / a sell
MT5 data only: the EA's bar exports plus the running terminal for the latest bars (read-only).
"""
from __future__ import annotations

import csv
import glob
import json
import math
from pathlib import Path

import numpy as np

FILES = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files")
EA = FILES / "EnterpriseEA"
DATA = Path(__file__).resolve().parent / "data"
TRACKED = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF", "CNY"}
FX = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP", "AUDJPY"]
CCY = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
FROM_YEAR = 2016


def news():
    rows = []
    for f in sorted(glob.glob(str(EA / "research" / "calendar" / "calendar_*.csv"))):
        if int(Path(f).stem.split("_")[1]) < FROM_YEAR:
            continue
        for r in csv.DictReader(open(f, encoding="utf-8", errors="replace")):
            if r["importance"] != "HIGH" or r["currency"] not in TRACKED:
                continue
            name = r["name"].replace(";", " ").replace("\n", " ")
            rows.append((int(r["time_server"]), r["currency"], int(r["sector"]), name))
    rows.sort()
    out = FILES / "S07Tester_news.csv"
    with open(out, "w", encoding="ascii", errors="replace", newline="") as fh:
        fh.write("time_server;currency;sector;name\r\n")
        for t, c, s, n in rows:
            fh.write(f"{t};{c};{s};{n}\r\n")
    print(f"news: {len(rows)} HIGH events -> {out}")


def broker_names():
    reg = json.load(open(EA / "current" / "symbol_registry.json", encoding="utf-8"))
    return {s["canonical_symbol"]: s["broker_symbol"] for s in reg.get("symbols", [])}


def h1(symbol, names):
    rows = {}
    f = DATA / f"bars_{symbol}_H1.csv"
    if f.exists():
        for r in csv.DictReader(open(f)):
            rows[int(r["time"])] = (float(r["high"]), float(r["low"]), float(r["close"]))
    try:
        import MetaTrader5 as mt5
        if mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
            for name in [names.get(symbol, ""), symbol + "-VIP", symbol, "US500" if symbol == "SP500" else ""]:
                if not name:
                    continue
                mt5.symbol_select(name, True)
                r = mt5.copy_rates_from_pos(name, mt5.TIMEFRAME_H1, 1, 20000)
                if r is not None and len(r):
                    for x in r:
                        rows[int(x["time"])] = (float(x["high"]), float(x["low"]), float(x["close"]))
                    break
            mt5.shutdown()
    except Exception as exc:
        print(symbol, "terminal tail skipped:", exc)
    t = np.array(sorted(rows), dtype=np.int64)
    a = np.array([rows[k] for k in t]) if len(t) else np.zeros((0, 3))
    return t, a


def measure(t, a, at):
    """EEA_SentMeasure on the 40 closed H1 bars up to `at` (bar open time) of one pair: (z4, z24) or None."""
    k = int(np.searchsorted(t, at, side="right"))
    if k < 40 or at - t[k - 1] > 6 * 3600:
        return None
    hh, ll, cc = a[k - 40:k, 0], a[k - 40:k, 1], a[k - 40:k, 2]
    tr = 0.0
    for i in range(40 - 14, 40):
        tr += max(hh[i], cc[i - 1]) - min(ll[i], cc[i - 1])
    atr = tr / 14.0
    if atr <= 0:
        return None
    c0 = cc[-1]
    return (c0 - cc[-5]) / (atr * 2.0), (c0 - cc[-25]) / (atr * math.sqrt(24.0))


def sentiment():
    names = broker_names()
    series = {s: h1(s, names) for s in FX + ["SP500", "XAUUSD"]}
    gt, _ = series["XAUUSD"]
    start = int(np.datetime64("2024-02-20").astype("datetime64[s]").astype(np.int64))
    out = FILES / "S07Tester_sentiment.csv"
    n_ok = 0
    with open(out, "w", newline="") as fh:
        fh.write("time_server;ok;a4;a24;ag4_buy;ag24_buy;ag4_sell;ag24_sell\r\n")
        for at in gt[gt >= start]:
            z = {s: measure(*series[s], at) for s in series}
            s4 = np.zeros(8); s24 = np.zeros(8); n = np.zeros(8)
            fx_pairs = 0
            for s in FX:
                if z[s] is None:
                    continue
                b, q = CCY.index(s[:3]), CCY.index(s[3:])
                s4[b] += z[s][0]; s24[b] += z[s][1]; n[b] += 1
                s4[q] -= z[s][0]; s24[q] -= z[s][1]; n[q] += 1
                fx_pairs += 1
            ok = fx_pairs >= 4 and n[0] >= 3
            if not ok:
                fh.write(f"{at};0;0;0;0;0;0;0\r\n")
                continue
            for i in range(8):
                if n[i] > 0:
                    s4[i] /= n[i]; s24[i] /= n[i]
            r4 = s4[3] + s4[6]; r24 = s24[3] + s24[6]; parts = 2
            if z["XAUUSD"] is not None:
                r4 += z["XAUUSD"][0]; r24 += z["XAUUSD"][1]; parts += 1
            if z["SP500"] is not None:
                r4 -= z["SP500"][0]; r24 -= z["SP500"][1]; parts += 1
            reg4, reg24 = r4 / parts, r24 / parts
            a4 = -s4[0] + 0.5 * reg4          # buy gold; a sell is the negative
            a24 = -s24[0] + 0.5 * reg24
            ag = {}
            for d in (1, -1):
                for k, h24 in ((4, False), (24, True)):
                    total = against = 0
                    for s in FX:
                        if z[s] is None or "USD" not in (s[:3], s[3:]):
                            continue
                        zz = z[s][1] if h24 else z[s][0]
                        support = (-d) * zz if s[:3] == "USD" else d * zz      # sign1 = -direction on USD
                        total += 1
                        against += support < 0
                    ag[(d, k)] = against / total if total else 0.0
            n_ok += 1
            fh.write(f"{at};1;{a4:.4f};{a24:.4f};{ag[(1, 4)]:.3f};{ag[(1, 24)]:.3f};{ag[(-1, 4)]:.3f};{ag[(-1, 24)]:.3f}\r\n")
    print(f"sentiment: {n_ok} H1 bars with a reading -> {out}")


if __name__ == "__main__":
    news()
    sentiment()
