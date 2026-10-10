"""MKT02: US-session setups on M15 for US indices and crypto - opening-range breakout (ORB), overnight gap fill
(GAP), VWAP reversion (VWR). Pre-registered plan: docs/superpowers/plans/2026-10-11-mkt02-session-setups.md.
MT5 data only (research/long/data/m15v, built by mkt01_data.py). Server clock = New York + 7 h all year.

  python mkt02_session.py
"""
from __future__ import annotations

import csv
import itertools
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "long" / "data"
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-mkt02-session-setups.md"
GROUPS = {"Chỉ số": ("NAS100", "DJ30", "SP500"), "Crypto lớn": ("BTCUSD", "ETHUSD")}
ALTS = ("SOLUSD", "XRPUSD", "LTCUSD")
OPEN, CLOSE = 16 * 3600 + 1800, 23 * 3600        # server seconds of day: NY 09:30 and 16:00
M15 = 900
PENALTY = 0.10


def srv(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())   # server-clock dates compared as naive


SEL0, SEL1, TEST1 = srv(2024, 2, 20), srv(2025, 7, 1), srv(2026, 10, 10)
BTC_OOS0 = srv(2022, 10, 1)
VARIANTS = {
    "ORB": list(itertools.product((15, 30), ("far", "mid"), ("2R", "EOD"))),
    "GAP": list(itertools.product((0.3, 0.6), ("full", "half"))),
    "VWR": list(itertools.product((3.0, 4.0), (False, True))),
}


# ---------------------------------------------------------------------------
_B: dict = {}


def bars(sym):
    if sym not in _B:
        meta = json.loads((DATA / "mkt01_meta.json").read_text())
        pt = float(meta[sym]["point"])
        rows = list(csv.DictReader(open(DATA / "m15v" / f"{sym}.csv")))
        B = [{"t": int(r["time"]), "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
              "c": float(r["close"]), "v": float(r["tickvol"] or 0), "sp": float(r["spread"]) * pt} for r in rows]
        recent = [b["sp"] for b in B if b["t"] >= SEL0]
        med = statistics.median(recent or [b["sp"] for b in B])
        for i, b in enumerate(B):
            b["sp"] = max(b["sp"], med)
            pc = B[i - 1]["c"] if i else b["c"]
            b["tr"] = max(b["h"], pc) - min(b["l"], pc)
        a = 0.0
        for i, b in enumerate(B):
            a = b["tr"] if i == 0 else a + (b["tr"] - a) / 14
            b["atr"] = a
        days = {}
        for i, b in enumerate(B):
            days.setdefault(b["t"] // 86400, []).append(i)
        _B[sym] = (B, days, med)
    return _B[sym]


def at(B, idx, sec):
    """Index of the bar starting at server second-of-day `sec` within a day's index list, or None."""
    for i in idx:
        if B[i]["t"] % 86400 == sec:
            return i
    return None


def walk(B, e, d, stop, target, end_t, med):
    """Enter at the open of bar e; stop first, then target, inside a bar; flat at end_t (open of that bar)."""
    entry = B[e]["o"] + (B[e]["sp"] if d == 1 else 0.0) + d * 0.5 * med
    risk = d * (entry - stop)
    if risk <= 0:
        return None
    if target is not None and d * (target - entry) <= 0:
        return None
    px = None
    for j in range(e, len(B)):
        b = B[j]
        if b["t"] >= end_t:
            px = b["o"] + (b["sp"] if d == -1 else 0.0)
            break
        sp = b["sp"] if d == -1 else 0.0
        hi, lo = b["h"] + sp, b["l"] + sp
        if (d == 1 and lo <= stop) or (d == -1 and hi >= stop):
            o = b["o"] + sp
            px = min(stop, o) if d == 1 else max(stop, o)
            break
        if target is not None and ((d == 1 and hi >= target) or (d == -1 and lo <= target)):
            px = target
            break
    if px is None:
        return None
    px -= d * 0.5 * med
    return d * (px - entry) / risk


def day_range(B, days, day, n=20):
    vals = []
    for k in range(day - 1, day - 40, -1):
        idx = days.get(k)
        if not idx:
            continue
        vals.append(max(B[i]["h"] for i in idx) - min(B[i]["l"] for i in idx))
        if len(vals) == n:
            break
    return statistics.fmean(vals) if len(vals) >= 10 else 0.0


def trades(sym, setup, var):
    B, days, med = bars(sym)
    out = []
    keys = sorted(days)
    for di, day in enumerate(keys):
        idx = days[day]
        o = at(B, idx, OPEN)
        if o is None:
            continue
        end_t = day * 86400 + CLOSE
        r = None
        d = 0
        if setup == "ORB":
            n, sl, ex = var
            k = n // 15
            rng = [o + j for j in range(k)]
            if rng[-1] >= len(B) or B[rng[-1]]["t"] != B[o]["t"] + (k - 1) * M15:
                continue
            hi, lo = max(B[i]["h"] for i in rng), min(B[i]["l"] for i in rng)
            for s in range(rng[-1] + 1, len(B) - 1):
                if B[s]["t"] >= B[o]["t"] + 2 * 3600 + n * 60 or B[s]["t"] >= end_t:
                    break
                c = B[s]["c"]
                if c > hi or c < lo:
                    d = 1 if c > hi else -1
                    stop = (lo if d == 1 else hi) if sl == "far" else (hi + lo) / 2
                    e = s + 1
                    entry = B[e]["o"] + (B[e]["sp"] if d == 1 else 0.0) + d * 0.5 * med
                    tgt = entry + 2 * (entry - stop) if ex == "2R" else None
                    r = walk(B, e, d, stop, tgt, end_t, med)
                    break
        elif setup == "GAP":
            k, tg = var
            prev = None
            for pk in keys[max(0, di - 4):di][::-1]:
                p = at(B, days[pk], CLOSE - M15)
                if p is not None:
                    prev = B[p]["c"]
                    break
            dr = day_range(B, days, day)
            if prev is None or dr <= 0:
                continue
            gap = B[o]["o"] - prev
            if abs(gap) < k * dr:
                continue
            d = -1 if gap > 0 else 1
            stop = B[o]["o"] - d * abs(gap)
            tgt = prev if tg == "full" else (prev + B[o]["o"]) / 2
            r = walk(B, o, d, stop, tgt, end_t, med)
        else:
            z, rev = var
            pv = vv = 0.0
            for s in range(o, len(B) - 1):
                b = B[s]
                if b["t"] >= end_t - M15:
                    break
                w = max(b["v"], 1.0)
                pv += w * (b["h"] + b["l"] + b["c"]) / 3
                vv += w
                vwap = pv / vv
                sec = b["t"] % 86400
                if sec + M15 < 17 * 3600 or sec + M15 > 22 * 3600 or b["atr"] <= 0:
                    continue
                dist = b["c"] - vwap
                if abs(dist) < z * b["atr"]:
                    continue
                d = -1 if dist > 0 else 1
                if rev and d * (b["c"] - b["o"]) <= 0:
                    continue
                w3 = B[s - 2:s + 1]
                stop = (max(x["h"] for x in w3) + 0.1 * b["atr"]) if d == -1 else (min(x["l"] for x in w3) - 0.1 * b["atr"])
                r = walk(B, s + 1, d, stop, vwap, end_t, med)
                break
        if r is not None:
            t = B[o]["t"]
            out.append({"r": r, "t": t, "sym": sym, "d": d})
    return out


# ---------------------------------------------------------------------------
def mean(x):
    return statistics.fmean(x) if x else 0.0


def lower(xs, q, runs=4000, seed=102):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(q * runs)]


def dd_r(rs):
    eq = pk = dd = 0.0
    for r in rs:
        eq += r
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dd


def cell(rows):
    return f"{len(rows)} / {mean([r['r'] for r in rows]):+.3f}" if rows else "—"


def vname(setup, v):
    if setup == "ORB":
        return f"{v[0]}′ / SL {'xa' if v[1] == 'far' else 'giữa'} / {v[2]}"
    if setup == "GAP":
        return f"k {v[0]} / {'lấp hết' if v[1] == 'full' else 'lấp nửa'}"
    return f"z {v[0]:.0f} / {'cần nến đảo' if v[1] else 'không cần nến đảo'}"


def sanity():
    """NY open check: median M15 range at 16:30 server vs 16:00 server (NAS100)."""
    B, days, _ = bars("NAS100")
    a = [b["h"] - b["l"] for b in B if b["t"] % 86400 == OPEN]
    c = [b["h"] - b["l"] for b in B if b["t"] % 86400 == OPEN - 1800]
    return statistics.median(a) / statistics.median(c)


def main():
    L = ["# MKT02: setup theo phiên Mỹ cho chỉ số và crypto — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-mkt02-session-setups.md`. M15, chi phí khắt khe (ask/bid + trượt 0,5 × spread trung vị "
         "mỗi chiều), phí hoa hồng 0. Ô: số lệnh / R mỗi lệnh. Chọn: 02/2024–06/2025; test: 07/2025–10/2026.", ""]
    L.append(f"Kiểm tra giờ: biên độ nến M15 lúc 16:30 server (mở cửa NY) = {sanity():.1f}× nến 16:00 (NAS100).")
    L.append("")
    finals = []
    for setup, vs in VARIANTS.items():
        for gname, syms in GROUPS.items():
            L += [f"## {setup} — {gname}", "", "| Biến thể | Chọn: nửa 1 | Chọn: nửa 2 | Chọn: cả kỳ | Đạt? | Test |",
                  "|---|---|---|---|---|---|"]
            mid = (SEL0 + SEL1) // 2
            best, bscore, rows_of = None, None, {}
            for v in vs:
                rows = [t for s in syms for t in trades(s, setup, v)]
                rows_of[v] = rows
                a = [r for r in rows if SEL0 <= r["t"] < mid]
                b = [r for r in rows if mid <= r["t"] < SEL1]
                sel = a + b
                ok = len(sel) >= 60 and mean([r["r"] for r in sel]) > 0 and mean([r["r"] for r in a]) > 0 and mean([r["r"] for r in b]) > 0
                if ok and (bscore is None or mean([r["r"] for r in sel]) > bscore):
                    best, bscore = v, mean([r["r"] for r in sel])
                test = [r for r in rows if SEL1 <= r["t"] < TEST1]
                L.append(f"| {vname(setup, v)} | {cell(a)} | {cell(b)} | {cell(sel)} | {'đạt' if ok else ''} | {cell(test)} |")
            L.append("")
            if best is None:
                L += [f"**{setup} — {gname}: không biến thể nào đạt → dừng.**", ""]
            else:
                L += [f"Chọn: **{vname(setup, best)}**.", ""]
                finals.append((setup, gname, best, rows_of[best]))
            print(setup, gname, best, flush=True)
    L += ["## Kiểm tra cuối (07/2025–10/2026)", "",
          "| Ô | Biến thể | Lệnh | R/lệnh | Cận dưới 90% | Cận dưới 98,3% | Sau trừ 0,10R | %/năm @0,5% | DD @0,5% | Theo symbol | Đạt? |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    yrs = (TEST1 - SEL1) / (365.25 * 86400)
    for setup, gname, v, rows in finals:
        test = sorted([r for r in rows if SEL1 <= r["t"] < TEST1], key=lambda r: r["t"])
        rs = [r["r"] for r in test]
        if len(rs) < 2:
            L.append(f"| {setup} {gname} | {vname(setup, v)} | {len(rs)} | | | | | | | | không |")
            continue
        m, l90, lb, mp = mean(rs), lower(rs, 0.10), lower(rs, 0.10 / 6), mean(rs) - PENALTY
        ok = m > 0 and l90 > 0 and mp > 0
        per = ", ".join(f"{s} {cell([r for r in test if r['sym'] == s])}" for s in GROUPS[gname])
        L.append(f"| {setup} {gname} | {vname(setup, v)} | {len(rs)} | {m:+.3f} | {l90:+.3f} | {lb:+.3f} | {mp:+.3f} | "
                 f"{sum(rs) * 0.5 / yrs:+.1f} | {dd_r(rs) * 0.5:.1f}% | {per} | "
                 f"{'**ĐẠT**' + (' (cả Bonferroni)' if lb > 0 else '') if ok else 'không'} |")
    L.append("")
    crypto = [f for f in finals if f[1] == "Crypto lớn"]
    if crypto:
        L += ["## BTC ngoài mẫu thêm (10/2022–02/2024) và altcoin (biến thể đã chọn của nhóm crypto)", "",
              "| Setup | Biến thể | BTC 10/2022–02/2024 | SOL (mọi kỳ) | XRP (mọi kỳ) | LTC (mọi kỳ) |", "|---|---|---|---|---|---|"]
        for setup, _, v, _ in crypto:
            btc = [r for r in trades("BTCUSD", setup, v) if BTC_OOS0 <= r["t"] < SEL0]
            alts = [cell(trades(s, setup, v)) for s in ALTS]
            L.append(f"| {setup} | {vname(setup, v)} | {cell(btc)} | " + " | ".join(alts) + " |")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
