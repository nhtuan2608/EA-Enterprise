"""G93: S04 and S06B(_USD) on EURUSD/GBPUSD at M15/M30/H1 - variants (zones, box, contraction, exits, USD flow),
indicator filters scored as G79, test on each timeframe's last period. Pre-registered plan:
docs/superpowers/plans/2026-10-11-g93-s04-s06b-fx.md. MT5 data only.

  python g93_s04_s06b_fx.py
"""
from __future__ import annotations

import bisect
import itertools
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_study as ls  # noqa: E402,F401  (sets the research data path)
import context  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import g92_s04_plus as g92  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

REPORT = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "reports" / "2026-10-11-g93-s04-s06b-fx.md"
SYMBOLS = ("EURUSD", "GBPUSD")
PENALTY = 0.10


def utc(y, m=1, d=1):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


# timeframe -> (profile, context start, validate start, test start, end)
TFS = {"H1": ("SWING", utc(2010), utc(2017), utc(2021), utc(2025, 10, 10)),
       "M30": ("SWINGM30", utc(2017, 10, 1), utc(2020), utc(2022), utc(2025, 10, 10)),
       "M15": ("SWINGM15", utc(2021, 10, 10), utc(2023), utc(2024), utc(2025, 10, 10))}

# M15 entries with H1 levels, M30 entries with H4 levels; same level depth and trade management as SWING,
# managed on the entry timeframe's own bars (as the EA does).
context.ENTRY_TF.update(SWINGM15="M15", SWINGM30="M30")
context.LEVEL_TF.update(SWINGM15="H1", SWINGM30="H4")
context.LEVEL_BARS.update(SWINGM15=320, SWINGM30=320)
context.SWING_LOOKBACK.update(SWINGM15=240, SWINGM30=240)
context.TF_SECONDS.update(M15=900, M30=1800)
for _p in ("SWINGM15", "SWINGM30"):
    replay.TM[_p], replay.HORIZON[_p], replay.MIN_RR[_p] = replay.TM["SWING"], replay.HORIZON["SWING"], 2.0

S04_EXITS = {"T0": {"costs": True}, "T1": {"costs": True, "target": "fixed", "fixed_r": 2.0},
             "T2": {"costs": True, "target": "fixed", "fixed_r": 1.5, "min_rr": 1.5, "tm": False}}
S06_EXITS = {"X3": {"costs": True, "target": "fixed", "fixed_r": 3.0, "min_rr": 3.0},
             "X2": {"costs": True, "target": "fixed", "fixed_r": 2.0, "min_rr": 2.0},
             "X15": {"costs": True, "target": "fixed", "fixed_r": 1.5, "min_rr": 1.5, "tm": False}}
S04_VARIANTS = [(z, e) for z in ("Z0", "Z1") for e in S04_EXITS]
S06_VARIANTS = list(itertools.product((12, 24), (0.85, 0.70), S06_EXITS, ("U0", "U1")))
FILTERS = {"S04": ("F1", "F2", "F3", "F4", "F5", "F6", "F7"), "S06": ("F1", "F2", "F3", "F4", "F5", "F6")}
MIN_TV = 60


def period(tf, u):
    _, start, val, test, end = TFS[tf]
    if u < start or u >= end:
        return None
    return "train" if u < val else "validate" if u < test else "test"


# ---------------------------------------------------------------------------
# contexts and labels
# ---------------------------------------------------------------------------
_CTX: dict = {}


def ctx_for(symbol, tf, zone="Z0"):
    key = (symbol, tf, zone)
    if key not in _CTX:
        profile, start = TFS[tf][0], TFS[tf][1]
        _CTX[key] = context.build(symbol, profile, start) if zone == "Z0" else g92.all_zone_ctx(symbol, profile)
    return _CTX[key]


_USD = None
_IND: dict = {}


def indicators(symbol, tf):
    if (symbol, tf) not in _IND:
        bars = ctx_for(symbol, tf)["entry"]
        closes = [b["close"] for b in bars]
        _IND[(symbol, tf)] = {"adx": filters.adx(bars), "e21": filters.ema(closes, 21), "e55": filters.ema(closes, 55),
                              "e100": filters.ema(closes, 100), "times": [b["time"] for b in bars]}
    return _IND[(symbol, tf)]


def usd_flow(t_close):
    """USD flow of the last H1 bar closed at or before t_close (server time)."""
    global _USD
    if _USD is None:
        _USD = filters.usd_index()
    h = t_close - t_close % 3600 - 3600
    return _USD.get(h, 0)


_PD: dict = {}


def prior_days(symbol, tf):
    if (symbol, tf) not in _PD:
        _PD[(symbol, tf)] = g92.prior_days(ctx_for(symbol, tf))
    return _PD[(symbol, tf)]


def labels(symbol, tf, ctx, c):
    """Labels at the signal bar's close. ADX / EMAs come from the Z0 context bars (same bar list for Z1)."""
    i, d = c["i"], c["direction"]
    b = ctx["entry"][i]
    ind = indicators(symbol, tf)
    j = i if ind["times"][i] == b["time"] else bisect.bisect_left(ind["times"], b["time"])
    sec = context.TF_SECONDS[tf]
    flow = usd_flow(b["time"] + sec)
    prev = prior_days(symbol, tf).get(b["utc"] // 86400 - 1)
    return {"F1": replay.htf_aligned(c["structure"], d),
            "F2": g92.h4_side(symbol, b["time"]) == d,
            "F3": 7 <= (b["utc"] // 3600) % 24 < 17,
            "F4": flow != 0 and d == filters.USD_SIGN[symbol] * flow,
            "F5": ind["adx"][j] > 20,
            "F6": d * (ind["e21"][j] - ind["e55"][j]) > 0 and d * (ind["e55"][j] - ind["e100"][j]) > 0,
            "F7": prev is not None and ((d == -1 and c["extreme"] > prev[0]) or (d == 1 and c["extreme"] < prev[1]))}


# ---------------------------------------------------------------------------
# trades
# ---------------------------------------------------------------------------
_CANDS: dict = {}


def cands(symbol, tf, setup, var):
    if setup == "S04":
        zone = var[0]
        key = (symbol, tf, "S04", zone)
        if key not in _CANDS:
            ctx = ctx_for(symbol, tf, zone)
            cs = [x for x in replay.candidates(ctx, "S04", replay.engine_params("S04", TFS[tf][0]))
                  if x.get("kind") != "LIMIT"]
            _CANDS[key] = (ctx, [(c, labels(symbol, tf, ctx, c)) for c in cs])
    else:
        box, con = var[0], var[1]
        key = (symbol, tf, "S06", box, con)
        if key not in _CANDS:
            ctx = ctx_for(symbol, tf)
            p = dict(filters.S06B, box=box, contraction=con)
            _CANDS[key] = (ctx, [(c, labels(symbol, tf, ctx, c)) for c in setups.s06(ctx, p)])
    return _CANDS[key]


def trades(symbol, tf, setup, var, keep=()):
    """One trade at a time; candidates failing a required label are never taken (as the EA would)."""
    ctx, cs = cands(symbol, tf, setup, var)
    need = tuple(keep) + (("F4",) if setup == "S06" and var[3] == "U1" else ())
    ex = S04_EXITS[var[1]] if setup == "S04" else S06_EXITS[var[2]]
    out, free = [], -1
    for c, lab in cs:
        if c["i"] <= free or not all(lab[f] for f in need):
            continue
        u = ctx["entry"][c["i"]]["utc"]
        p = period(tf, u)
        if p is None:
            continue
        r = replay.evaluate(ctx, c, "S04" if setup == "S04" else "S06", TFS[tf][0], "tm", ex)
        if r["status"] != "EVALUATED":
            continue
        free = r.get("exit_i", c["i"])
        out.append({"r": r["r"], "utc": u, "p": p, "sym": symbol, "lab": lab})
    return out


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def mean(x):
    return statistics.fmean(x) if x else 0.0


def lower(xs, q, runs=4000, seed=93):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(q * runs)]


def streak(rs):
    best = cur = 0
    for r in rs:
        cur = cur + 1 if r < 0 else 0
        best = max(best, cur)
    return best


def dd_r(rs):
    eq = pk = dd = 0.0
    for r in rs:
        eq += r
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dd


def cell(rows, q):
    x = [r["r"] for r in rows if r["p"] == q]
    return f"{len(x)} / {mean(x):+.3f}" if x else "—"


def vname(setup, var):
    return "/".join(var) if setup == "S04" else f"hộp{var[0]}/nén{var[1]:.2f}/{var[2]}/{var[3]}"


def out(L, line=""):
    L.append(line)
    sys.stdout.buffer.write((line + "\n").encode())
    sys.stdout.flush()


# ---------------------------------------------------------------------------
def part0(L):
    usd, dxy = filters.usd_index(), filters.real_dxy()
    out(L, "## Phần 0 — vì sao S06B_USD biến động (sổ G55, H1, 2010–10/2025)")
    out(L)
    out(L, "| Cặp | Lệnh | Thắng | R thắng TB | R thua TB | R/lệnh không nhồi | R/lệnh có nhồi | Chuỗi thua dài nhất | DD lớn nhất (R, có nhồi) |")
    out(L, "|---|---|---|---|---|---|---|---|---|")
    years = {}
    for s in SYMBOLS:
        c = ls.ctx(s, "SWING")
        ts = sorted(exits.trades("S06B_USD", s, usd, dxy), key=lambda t: t["utc"])
        pr = [pyramid.run(c, t, pyramid.CURRENT)["r"] for t in ts]
        nr = [t["r_replay"] for t in ts]
        w = [r for r in pr if r > 0]
        lo = [r for r in pr if r <= 0]
        out(L, f"| {s} | {len(pr)} | {len(w) / max(len(pr), 1):.0%} | {mean(w):+.2f} | {mean(lo):+.2f} | {mean(nr):+.3f} | "
               f"{mean(pr):+.3f} | {streak(pr)} | {dd_r(pr):.1f} |")
        for t, r in zip(ts, pr):
            y = datetime.fromtimestamp(t["utc"], timezone.utc).year
            years.setdefault(y, {}).setdefault(s, []).append(r)
    out(L)
    out(L, "R theo năm (có nhồi; lệnh / tổng R):")
    out(L)
    out(L, "| Năm | " + " | ".join(SYMBOLS) + " |")
    out(L, "|---|" + "---|" * len(SYMBOLS))
    for y in sorted(years):
        out(L, f"| {y} | " + " | ".join(f"{len(years[y].get(s, []))} / {sum(years[y].get(s, [])):+.1f}" for s in SYMBOLS) + " |")
    out(L)


def main():
    L = []
    out(L, "# G93: S04 và S06B_USD cho EURUSD/GBPUSD ở M15/M30/H1 — kết quả")
    out(L)
    out(L, "Kế hoạch: `plans/2026-10-11-g93-s04-s06b-fx.md`. EURUSD + GBPUSD gộp, chi phí như G55, một lệnh mỗi lúc trên "
           "mỗi biến thể × cặp. Ô: số lệnh / R mỗi lệnh.")
    out(L)
    part0(L)
    finals = []
    for setup, variants in (("S04", S04_VARIANTS), ("S06", S06_VARIANTS)):
        for tf in ("H1", "M30", "M15"):
            out(L, f"## {setup} {tf} — Phần A (biến thể)")
            out(L)
            out(L, "| Biến thể | Train | Validate | Đạt? | Test |")
            out(L, "|---|---|---|---|---|")
            best, best_score, rows_of = None, None, {}
            for var in variants:
                rows = [t for s in SYMBOLS for t in trades(s, tf, setup, var)]
                rows_of[var] = rows
                tr = [r["r"] for r in rows if r["p"] == "train"]
                va = [r["r"] for r in rows if r["p"] == "validate"]
                ok = bool(tr) and bool(va) and mean(tr) > 0 and mean(va) > 0 and len(tr) + len(va) >= MIN_TV
                if ok and (best_score is None or min(mean(tr), mean(va)) > best_score):
                    best, best_score = var, min(mean(tr), mean(va))
                out(L, f"| {vname(setup, var)} | {cell(rows, 'train')} | {cell(rows, 'validate')} | {'đạt' if ok else ''} | "
                       f"{cell(rows, 'test')} |")
            out(L)
            if best is None:
                out(L, f"**{setup} {tf}: không biến thể nào đạt → dừng.**")
                out(L)
                continue
            out(L, f"Chọn: **{vname(setup, best)}** (min train/validate {best_score:+.3f}).")
            out(L)
            rows = rows_of[best]
            tv = [r for r in rows if r["p"] != "test"]
            out(L, "| Lọc | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ lệnh | Giữ lọc? |")
            out(L, "|---|---|---|---|---|")
            kept, gaps = [], {}
            for f in FILTERS[setup]:
                if f == "F4" and setup == "S06" and best[3] == "U1":
                    continue
                ok, cells, gap = True, [], []
                for q in ("train", "validate"):
                    a = [r["r"] for r in rows if r["p"] == q and r["lab"][f]]
                    b = [r["r"] for r in rows if r["p"] == q and not r["lab"][f]]
                    cells.append(f"{len(a)} {mean(a):+.2f} / {len(b)} {mean(b):+.2f}")
                    ok = ok and bool(a) and bool(b) and mean(a) > mean(b)
                    gap.append(mean(a) - mean(b))
                share = sum(1 for r in tv if r["lab"][f]) / max(len(tv), 1)
                ok = ok and share >= 0.4
                if ok:
                    kept.append(f)
                    gaps[f] = mean(gap)
                out(L, f"| {f} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} |")
            sel = [t for s in SYMBOLS for t in trades(s, tf, setup, best, kept)]
            if kept and len([r for r in sel if r["p"] != "test"]) < 30:
                kept = [max(gaps, key=gaps.get)]
                sel = [t for s in SYMBOLS for t in trades(s, tf, setup, best, kept)]
            out(L)
            out(L, f"Áp lọc **{', '.join(kept) or 'không'}** (chạy lại một lệnh mỗi lúc): train {cell(sel, 'train')}, "
                   f"validate {cell(sel, 'validate')}, **test {cell(sel, 'test')}**.")
            out(L)
            finals.append((setup, tf, best, kept, sel))
    out(L, "## Kiểm tra cuối (kỳ test từng khung)")
    out(L)
    out(L, "| Ô | Biến thể + lọc | Lệnh test | Lệnh/năm | R/lệnh | Cận dưới 90% | Cận dưới 98,3% | Sau trừ 0,10R | %/năm @0,5% | DD @0,5% | Chuỗi thua | EUR | GBP | Đạt? |")
    out(L, "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for setup, tf, best, kept, sel in finals:
        test = sorted([r for r in sel if r["p"] == "test"], key=lambda r: r["utc"])
        rs = [r["r"] for r in test]
        if len(rs) < 2:
            out(L, f"| {setup} {tf} | {vname(setup, best)} {'+'.join(kept)} | {len(rs)} | | | | | | | | | | | không |")
            continue
        yrs = (TFS[tf][4] - TFS[tf][3]) / (365.25 * 86400)
        m, l90, l98, mp = mean(rs), lower(rs, 0.10), lower(rs, 0.10 / 6), mean(rs) - PENALTY
        ok = m > 0 and l90 > 0 and mp > 0
        by = {s: [r["r"] for r in test if r["sym"] == s] for s in SYMBOLS}
        out(L, f"| {setup} {tf} | {vname(setup, best)} {'+'.join(kept) or '—'} | {len(rs)} | {len(rs) / yrs:.0f} | {m:+.3f} | "
               f"{l90:+.3f} | {l98:+.3f} | {mp:+.3f} | {sum(rs) * 0.5 / yrs:+.1f} | {dd_r(rs) * 0.5:.1f}% | {streak(rs)} | "
               f"{len(by['EURUSD'])} {mean(by['EURUSD']):+.2f} | {len(by['GBPUSD'])} {mean(by['GBPUSD']):+.2f} | "
               f"{'**ĐẠT**' + (' (cả Bonferroni)' if l98 > 0 else '') if ok else 'không'} |")
    out(L)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
