"""FX03: scheduled flows - home-hours depreciation (A) and the month-end London 4pm fix (B) on EURUSD, GBPUSD, USDJPY H1.
Pre-registered plan: docs/superpowers/plans/2026-10-11-fx03-structural-flows.md. MT5 data only.

  python fx03_flows.py
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "long"))
import g93_s04_s06b_fx as g93  # noqa: E402  (data path, H1 contexts with UTC and ATR)
import context  # noqa: E402
import filters  # noqa: E402
import replay  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-fx03-structural-flows.md"
SYMS = ("EURUSD", "GBPUSD", "USDJPY")
VALIDATE = datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp()
TEST = datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp()
END = datetime(2025, 10, 10, tzinfo=timezone.utc).timestamp()
PENALTY = 0.10
# code -> list of (variant name, {symbol: direction}, start hour UTC, end hour UTC)
A = {"A-EU": [(f"{s:02d}–{e:02d}", {"EURUSD": -1, "GBPUSD": -1}, s, e) for s, e in ((6, 11), (7, 12))],
     "A-US": [(f"{s:02d}–{e:02d}", {"EURUSD": 1, "GBPUSD": 1, "USDJPY": -1}, s, e) for s, e in ((12, 19), (13, 20))],
     "A-JP": [(f"{s:02d}–{e:02d}", {"USDJPY": 1}, s, e) for s, e in ((0, 6), (1, 7))]}


def period(t):
    return "train" if t < VALIDATE else "validate" if t < TEST else "test" if t < END else None


def uk_dst(utc):
    y = datetime.fromtimestamp(utc, timezone.utc).year

    def last_sunday(month):
        d = datetime(y, month + 1, 1, tzinfo=timezone.utc).timestamp() - 86400
        wd = datetime.fromtimestamp(d, timezone.utc).weekday()
        return d - ((wd + 1) % 7) * 86400

    return last_sunday(3) + 3600 <= utc < last_sunday(10) + 3600


_B: dict = {}


def bars_by_hour(sym):
    """utc hour start -> H1 bar (with ATR of the bar before)."""
    if sym not in _B:
        bars = g93.ctx_for(sym, "H1")["entry"]
        m = {}
        for i in range(1, len(bars)):
            b = dict(bars[i], prev_atr=bars[i - 1]["atr"])
            m[b["utc"] - b["utc"] % 3600] = b
        _B[sym] = m
    return _B[sym]


POINT = {s: float(context.meta()["by_symbol"][s]["point"]) for s in SYMS}


def trade(sym, d, t0, t1):
    """Open of the bar starting t0 -> close of the bar starting t1 - 3600 (UTC)."""
    m = bars_by_hour(sym)
    a, b = m.get(t0), m.get(t1 - 3600)
    if a is None or b is None or a["prev_atr"] <= 0:
        return None
    n = (t1 - t0) / 3600
    unit = a["prev_atr"] * math.sqrt(n)
    gross = d * (b["close"] - a["open"])
    cost = a["spread"] * POINT[sym] + replay.COMMISSION.get(sym, 0.0)
    return {"r": (gross - cost) / unit, "g": gross / unit, "utc": t0, "p": period(t0), "sym": sym}


def days():
    """Weekday UTC dates present in all three symbols' H1 bars."""
    sets = [set(t - t % 86400 for t in bars_by_hour(s)) for s in SYMS]
    return sorted(d for d in set.intersection(*sets) if datetime.fromtimestamp(d, timezone.utc).weekday() < 5)


def family_a(dirs, s, e):
    out = []
    for day in days():
        for sym, d in dirs.items():
            t = trade(sym, d, day + s * 3600, day + e * 3600)
            if t and t["p"]:
                out.append(t)
    return out


def usd_level(t):
    """USD index (mean of -log EURUSD, -log GBPUSD, +log USDJPY) at the close of the bar starting t - 3600."""
    v = []
    for s, sgn in (("EURUSD", -1), ("GBPUSD", -1), ("USDJPY", 1)):
        b = bars_by_hour(s).get(t - 3600)
        if b is None:
            return None
        v.append(sgn * math.log(b["close"]))
    return sum(v) / 3


def family_b(post):
    ds = days()
    last = {}
    for d in ds:
        dt = datetime.fromtimestamp(d, timezone.utc)
        last[(dt.year, dt.month)] = d
    out = []
    keys = sorted(last)
    for k0, k1 in zip(keys, keys[1:]):
        day = last[k1]
        start_prev = last[k0] + 86400          # first instant after the previous month's last trading day
        t10 = day + 10 * 3600
        fix = day + (15 if uk_dst(day + 12 * 3600) else 16) * 3600
        # previous month's last bar close: last available hour before start_prev
        base = None
        for h in range(0, 48):
            base = usd_level(start_prev - h * 3600)
            if base is not None:
                break
        now = usd_level(t10)
        if base is None or now is None or now == base:
            continue
        mtd = 1 if now > base else -1
        for sym in SYMS:
            sign = filters.USD_SIGN[sym]
            if post:
                t = trade(sym, sign * mtd, fix, fix + 4 * 3600)
            else:
                t = trade(sym, sign * -mtd, t10, fix)
            if t and t["p"]:
                out.append(t)
    return out


def main():
    out, mean, cell = g93.out, g93.mean, g93.cell
    L = []
    out(L, "# FX03: dòng tiền có cấu trúc — giờ trong ngày và chốt giá cuối tháng — kết quả")
    out(L)
    out(L, "Kế hoạch: `plans/2026-10-11-fx03-structural-flows.md`. H1, giờ UTC. R = lời/lỗ sau chi phí ÷ (ATR14 H1 × √giờ giữ). "
           "Ô: số lệnh / R mỗi lệnh (sau chi phí). Cột cuối: R trước chi phí, mọi kỳ.")
    out(L)
    out(L, "| Mã | Biến thể | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 | R trước chi phí (mọi kỳ) |")
    out(L, "|---|---|---|---|---|---|---|")
    cases = [(code, name, family_a(dirs, s, e)) for code, vs in A.items() for name, dirs, s, e in vs]
    cases += [("B-FIX", "10:00→chốt, ngược USD", family_b(False)), ("B-POST", "chốt→+4h, cùng USD", family_b(True))]
    best = {}
    for code, name, rows in cases:
        tr = [r["r"] for r in rows if r["p"] == "train"]
        va = [r["r"] for r in rows if r["p"] == "validate"]
        ok = bool(tr) and bool(va) and mean(tr) > 0 and mean(va) > 0 and len(tr) + len(va) >= 60
        if ok and (code not in best or min(mean(tr), mean(va)) > best[code][0]):
            best[code] = (min(mean(tr), mean(va)), name, rows)
        out(L, f"| {code} | {name} | {cell(rows, 'train')} | {cell(rows, 'validate')} | {'đạt' if ok else ''} | "
               f"{cell(rows, 'test')} | {mean([r['g'] for r in rows]):+.3f} |")
    out(L)
    out(L, "## Kiểm tra cuối (2021–10/2025)")
    out(L)
    if not best:
        out(L, "**Không mã nào qua bước chọn.**")
        out(L)
    else:
        out(L, "| Mã | Biến thể | Lệnh | R/lệnh | Cận dưới 90% | Cận dưới 98% | Sau trừ 0,10R | %/năm @0,5% | DD @0,5% | Theo cặp | Đạt? |")
        out(L, "|---|---|---|---|---|---|---|---|---|---|---|")
        yrs = (END - TEST) / (365.25 * 86400)
        for code, (_, name, rows) in best.items():
            test = sorted([r for r in rows if r["p"] == "test"], key=lambda r: r["utc"])
            rs = [r["r"] for r in test]
            m, l90, lb, mp = mean(rs), g93.lower(rs, 0.10), g93.lower(rs, 0.10 / 5), mean(rs) - PENALTY
            ok = m > 0 and l90 > 0 and mp > 0
            per = ", ".join(f"{s} {len([r for r in test if r['sym'] == s])} {mean([r['r'] for r in test if r['sym'] == s]):+.3f}"
                            for s in SYMS if any(r["sym"] == s for r in test))
            out(L, f"| {code} | {name} | {len(rs)} | {m:+.3f} | {l90:+.3f} | {lb:+.3f} | {mp:+.3f} | "
                   f"{sum(rs) * 0.5 / yrs:+.1f} | {g93.dd_r(rs) * 0.5:.1f}% | {per} | "
                   f"{'**ĐẠT**' + (' (cả Bonferroni)' if lb > 0 else '') if ok else 'không'} |")
            ys = {}
            for r in rows:
                ys.setdefault(datetime.fromtimestamp(r["utc"], timezone.utc).year, []).append(r["r"])
            out(L, f"| | R theo năm | " + "; ".join(f"{y} {sum(v):+.0f}" for y, v in sorted(ys.items())) + " | | | | | | | | |")
        out(L)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
