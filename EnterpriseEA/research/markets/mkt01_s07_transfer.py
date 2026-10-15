"""MKT01: the S07 book (G89 = S07Tester rules, chosen on XAUUSD) run unchanged on US indices and crypto.
Pre-registered plan: docs/superpowers/plans/2026-10-11-mkt01-s07-transfer.md. MT5 data only.

  python mkt01_s07_transfer.py            # every symbol (one child process each), then the report
  python mkt01_s07_transfer.py BTCUSD     # one symbol -> JSON on stdout
"""
from __future__ import annotations

import json
import random
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LONG = HERE.parent / "long"
sys.path.insert(0, str(LONG))
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-mkt01-s07-transfer.md"
SYMBOLS = ("BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "LTCUSD", "SP500", "NAS100", "DJ30")
PENALTY = 0.10
VARIANTS = {"full": dict(sides=(1, -1), early=True, re=True, adds=True),
            "buy": dict(sides=(1,), early=True, re=True, adds=True)}


def first_time(sym, tf):
    with open(LONG / "data" / f"{tf.lower()}v" / f"{sym}.csv") as fh:
        fh.readline()
        return int(fh.readline().split(",")[0])


def last_time(sym, tf):
    with open(LONG / "data" / f"{tf.lower()}v" / f"{sym}.csv", "rb") as fh:
        lines = fh.read().splitlines()
    return int(lines[-1].split(b",")[0])


def child(sym, start=None, end=None):
    import g67_dmi_ema as g
    meta = json.loads((LONG / "data" / "mkt01_meta.json").read_text())
    if sym != "XAUUSD":
        g.POINT[sym] = float(meta[sym]["point"])
        g.COMMISSION[sym] = 0.0
        orig = g.load
        g.load = lambda s: orig(sym if s == "XAUUSD" else s)
    import g89_full_book as b
    m30_0, m15_0 = first_time(sym, "M30"), first_time(sym, "M15")
    # server -> approx UTC (the bar loader's own conversion is used for every trade time)
    b.START = start or (m30_0 - 7200)
    b.SPLIT = max(b.START, m15_0 - 7200)
    b.END = end or (last_time(sym, "M30") + 1800)
    out = {"sym": sym, "start": b.START, "end": b.END}
    for name, var in VARIANTS.items():
        rows, legs = b.run(var)
        out[name] = [{"r": L["rh"], "ein": L["ein"], "eout": L["eout"], "w": L["w"], "kind": L["kind"], "d": L["d"]}
                     for L in legs]
    print(json.dumps(out))


def lower(xs, q, runs=4000, seed=101):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(q * runs)]


def equity(legs):
    eq = pk = 1.0
    dd = 0.0
    for L in sorted(legs, key=lambda x: x["eout"]):
        eq *= 1 + 0.015 * L["w"] * L["r"]
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    return eq, dd


def d(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%m/%Y")


def summary(res, name):
    legs = res[name]
    rs = [L["r"] for L in legs]
    if len(rs) < 2:
        return None
    mid = (res["start"] + res["end"]) / 2
    h1 = [L["r"] for L in legs if L["ein"] < mid]
    h2 = [L["r"] for L in legs if L["ein"] >= mid]
    yrs = (res["end"] - res["start"]) / (365.25 * 86400)
    eq, dd = equity(legs)
    return dict(n=len(rs), m=statistics.fmean(rs), h1=(len(h1), statistics.fmean(h1) if h1 else 0.0),
                h2=(len(h2), statistics.fmean(h2) if h2 else 0.0), l90=lower(rs, 0.10), lb=lower(rs, 0.10 / 8),
                py=(eq ** (1 / yrs) - 1) * 100 if eq > 0 else -100.0, dd=dd * 100, yrs=yrs,
                buy=statistics.fmean([L["r"] for L in legs if L["d"] == 1] or [0.0]),
                sell=statistics.fmean([L["r"] for L in legs if L["d"] == -1] or [0.0]),
                nb=sum(1 for L in legs if L["d"] == 1), ns=sum(1 for L in legs if L["d"] == -1))


def main():
    if len(sys.argv) > 1:
        a = sys.argv[1:]
        child(a[0], *(int(x) for x in a[1:]))
        return
    results = {}
    jobs = [(s, []) for s in SYMBOLS] + [("XAUUSD", [str(int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())),
                                                     str(int(datetime(2025, 10, 9, tzinfo=timezone.utc).timestamp()))])]
    for s, extra in jobs:
        p = subprocess.run([sys.executable, __file__, s, *extra], capture_output=True, text=True, cwd=str(HERE))
        if p.returncode != 0:
            print(s, "FAILED", p.stderr[-2000:])
            continue
        results[s] = json.loads(p.stdout.strip().splitlines()[-1])
        sm = summary(results[s], "full")
        print(s, sm and {k: (round(v, 3) if isinstance(v, float) else v) for k, v in sm.items()}, flush=True)
    L = ["# MKT01: bộ quy tắc S07 của vàng trên chỉ số Mỹ và crypto — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-mkt01-s07-transfer.md`. Sổ G89 (S07Tester) không chỉnh, chi phí khắt khe G68, "
         "phí hoa hồng 0. Toàn bộ là ngoài mẫu (quy tắc chọn trên XAUUSD). R/lệnh tính theo từng chân lệnh (gốc, vào sớm, "
         "vào lại, bồi); %/năm và DD ở 1,5% × trọng số, lãi kép.", "",
         "## Bản đầy đủ (mua + bán)", "",
         "| Symbol | Kỳ | Lệnh | R/lệnh | Nửa đầu | Nửa sau | Cận dưới 90% | Cận dưới 98,75% | Sau trừ 0,10R | Mua / Bán | %/năm | DD | Đạt? |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in list(SYMBOLS) + ["XAUUSD"]:
        if s not in results:
            L.append(f"| {s} | lỗi | | | | | | | | | | | |")
            continue
        sm = summary(results[s], "full")
        if sm is None:
            L.append(f"| {s} | | 0 | | | | | | | | | | không |")
            continue
        ok = sm["n"] >= 60 and sm["h1"][1] > 0 and sm["h2"][1] > 0 and sm["l90"] > 0 and sm["m"] - PENALTY > 0
        tag = ("**ĐẠT**" + (" (cả Bonferroni)" if sm["lb"] > 0 else "") if ok else "không") if s != "XAUUSD" else "đối chiếu"
        L.append(f"| {s} | {d(results[s]['start'])}–{d(results[s]['end'])} | {sm['n']} | {sm['m']:+.3f} | "
                 f"{sm['h1'][0]} / {sm['h1'][1]:+.3f} | {sm['h2'][0]} / {sm['h2'][1]:+.3f} | {sm['l90']:+.3f} | {sm['lb']:+.3f} | "
                 f"{sm['m'] - PENALTY:+.3f} | {sm['nb']} {sm['buy']:+.2f} / {sm['ns']} {sm['sell']:+.2f} | {sm['py']:+.1f}% | "
                 f"{sm['dd']:.0f}% | {tag} |")
    L += ["", "## Bản chỉ mua", "", "| Symbol | Lệnh | R/lệnh | Nửa đầu | Nửa sau | %/năm | DD |", "|---|---|---|---|---|---|---|"]
    for s in list(SYMBOLS) + ["XAUUSD"]:
        if s not in results:
            continue
        sm = summary(results[s], "buy")
        if sm:
            L.append(f"| {s} | {sm['n']} | {sm['m']:+.3f} | {sm['h1'][0]} / {sm['h1'][1]:+.3f} | {sm['h2'][0]} / {sm['h2'][1]:+.3f} | "
                     f"{sm['py']:+.1f}% | {sm['dd']:.0f}% |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    (HERE / "mkt01_results.json").write_text(json.dumps(results))


if __name__ == "__main__":
    main()
