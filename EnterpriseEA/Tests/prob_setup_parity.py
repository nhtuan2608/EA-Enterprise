"""MQL vs Python parity for ProbSetupEA: reads MQL5\\Files\\ProbSetupSelfTest.csv (written by Tests/ProbSetupSelfTest.mq5
on the terminal), loads the same closed bars read-only with the MetaTrader5 package, recomputes the signals with
Tests/prob_setup_oracle.py and the decisions from research/long/out/g114_frozen.json, and compares every field.

  python Tests/prob_setup_parity.py [path to ProbSetupSelfTest.csv]
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prob_setup_oracle as po  # noqa: E402

TERMINAL = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075")
CSV = TERMINAL / "MQL5" / "Files" / "ProbSetupSelfTest.csv"
FROZEN = HERE.parent / "research" / "long" / "out" / "g114_frozen.json"


def wilson(p, n, z=1.6448536269514722):
    if n <= 0:
        return 0.0
    return max(0.0, (p + z * z / (2 * n) - z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0))) / (1 + z * z / n))


def decide(fz: dict, fam: int, levels: list[int]) -> dict:
    f = next(x for x in fz["families"] if x["id"] == fam)
    s = f["base"] + sum(w["w"] for w in f["weights"] if levels[w["factor"]] == w["level"])
    blocks = f["blocks"]
    pick = 0
    for k, b in enumerate(blocks):
        if b["lo"] <= s:
            pick = k
    p, n = blocks[pick]["p"], blocks[pick]["n"]
    plo = wilson(p, n)
    ev = plo * f["W"] - (1 - plo) * f["L"]
    kel = 0.0 if ev <= 0 or f["var"] <= 0 else min(1.0, 0.25 * ev / f["var"])
    return dict(score=s, p=p, n=n, p_lo=plo, ev_lo=ev, kelly=kel, ok=int(ev > 0))


def rates(mt5, sym, tf, t0, t1):
    import datetime as dt
    r = mt5.copy_rates_range(sym, tf, dt.datetime.utcfromtimestamp(t0), dt.datetime.utcfromtimestamp(t1))
    return r


def main(path: Path = CSV) -> int:
    rows = list(csv.reader(path.open(encoding="ascii", errors="replace")))
    win = rows[0]
    sym = win[1]
    t = [int(x) for x in win[2:10]]
    point, unit_fail = float(win[10]), int(win[11])
    head = rows[1]
    M = [dict(zip(head, r)) for r in rows[2:] if r]
    import MetaTrader5 as mt5
    assert mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    tf = {15: mt5.TIMEFRAME_M15, 30: mt5.TIMEFRAME_M30, 5: mt5.TIMEFRAME_M5}[fz["tf_min"]]
    r = rates(mt5, sym, tf, t[0], t[1])
    h1 = rates(mt5, sym, mt5.TIMEFRAME_H1, t[2], t[3])
    h4 = rates(mt5, sym, mt5.TIMEFRAME_H4, t[4], t[5])
    d1 = rates(mt5, sym, mt5.TIMEFRAME_D1, t[6], t[7])
    mt5.shutdown()
    bars = {"time": [int(x) for x in r["time"]], "open": r["open"].tolist(), "high": r["high"].tolist(), "low": r["low"].tolist(),
            "close": r["close"].tolist(), "tickvol": r["tick_volume"].astype(float).tolist(), "sp": (r["spread"] * point).tolist()}
    fr = lambda x: {"time": [int(v) for v in x["time"]], "high": x["high"].tolist(), "low": x["low"].tolist(), "close": x["close"].tolist()}
    S = po.signals(bars, fr(h1), fr(h4), fr(d1), fz["tf_min"] * 60)
    n = len(bars["time"])
    py = {(s["j"], {"C1": 1, "C2": 2}[s["typ"]], s["d"]): s for s in S}
    mq = {(int(m["j"]), int(m["fam"]), int(m["d"])): m for m in M}
    bad = []
    if set(py) != set(mq):
        bad.append(f"signal sets differ: only python {sorted(set(py) - set(mq))[:5]}, only mql {sorted(set(mq) - set(py))[:5]}")
    fac = ["side", "sess", "d1", "h4", "adx", "vol", "div", "pos"]
    for k in sorted(set(py) & set(mq)):
        s, m = py[k], mq[k]
        for a in ("entry", "stop", "risk", "a30"):
            if abs(s[a] - float(m[a])) > 1e-6:
                bad.append((k, a, s[a], m[a]))
        lv = [s["f_" + f] for f in fac]
        if lv != [int(m[f]) for f in fac]:
            bad.append((k, "factors", lv, [m[f] for f in fac]))
        closed = s["exit_j"] < n - 1 or (s["j"] + 1 + po.MAX_BARS - 1 <= n - 1)
        if int(m["closed"]) == 1 and (not closed or abs(s["R"] - float(m["R"])) > 1e-6 or s["bars"] != int(m["bars"])):
            bad.append((k, "R", s["R"], m["R"], s["bars"], m["bars"]))
        d = decide(fz, k[1], lv)
        for a in ("score", "p", "n", "p_lo", "ev_lo", "kelly"):
            if abs(d[a] - float(m[a if a != "kelly" else "kelly"])) > 1e-7:
                bad.append((k, a, d[a], m[a]))
        if d["ok"] != int(m["ok"]):
            bad.append((k, "ok", d["ok"], m["ok"]))
    print(f"ProbSetupEA parity: {len(mq)} MQL signals, {len(py)} Python signals, {len(bad)} mismatches, MQL unit failures {unit_fail}")
    for b in bad[:10]:
        print("  ", b)
    return 0 if not bad and unit_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else CSV))
