"""FX02: currency strength on D1 (USD, EUR, GBP, JPY) - cross-sectional momentum (CSM), short-term cross-sectional
reversal (CSR), per-pair trend (TSM); crosses built from the majors. Pre-registered plan:
docs/superpowers/plans/2026-10-11-fx02-currency-strength.md. MT5 data only.

  python fx02_strength.py
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "long"))
import long_study as ls  # noqa: E402,F401  (sets the research data path)
import context  # noqa: E402
import filters  # noqa: E402
import g93_s04_s06b_fx as g93  # noqa: E402
import replay  # noqa: E402

REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-fx02-currency-strength.md"
MAJORS = ("EURUSD", "GBPUSD", "USDJPY")
PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY", "EURGBP")
CURS = ("USD", "EUR", "GBP", "JPY")
VALIDATE = datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp()
TEST = datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp()
END = datetime(2025, 10, 10, tzinfo=timezone.utc).timestamp()
PENALTY = 0.10
FAMILIES = {"CSM": [(L, H) for L in (20, 60, 120) for H in (5, 20)],
            "CSR": [(L, H) for L in (3, 5) for H in (1, 3)],
            "TSM": [(L, H) for L in (20, 60, 120) for H in (5, 20)]}
FILTERS = ("F1", "F2", "F3")


def period(t):
    return "train" if t < VALIDATE else "validate" if t < TEST else "test" if t < END else None


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load():
    m = context.meta()["by_symbol"]
    raw = {s: {b["time"]: b["close"] for b in context.load_bars(s, "D1")} for s in MAJORS}
    times = sorted(set.intersection(*(set(v) for v in raw.values())))
    px = {s: [raw[s][t] for t in times] for s in MAJORS}
    eu, gu, uj = px["EURUSD"], px["GBPUSD"], px["USDJPY"]
    px["EURJPY"] = [a * b for a, b in zip(eu, uj)]
    px["GBPJPY"] = [a * b for a, b in zip(gu, uj)]
    px["EURGBP"] = [a / b for a, b in zip(eu, gu)]
    cost = {}
    for s in MAJORS:
        sp = statistics.median(b["spread"] for b in context.load_bars(s, "H1")[-50000:])
        cost[s] = sp * float(m[s]["point"]) + replay.COMMISSION.get(s, 0.0)
    # per-bar round-trip cost of the synthetic crosses: both legs, in the cross's price units
    cst = {s: [cost[s]] * len(times) for s in MAJORS}
    cst["EURJPY"] = [cost["EURUSD"] * u + cost["USDJPY"] * e for e, u in zip(eu, uj)]
    cst["GBPJPY"] = [cost["GBPUSD"] * u + cost["USDJPY"] * g for g, u in zip(gu, uj)]
    cst["EURGBP"] = [cost["EURUSD"] / g + cost["GBPUSD"] * e / g ** 2 for e, g in zip(eu, gu)]
    point = {s: float(m[s]["point"]) for s in MAJORS}
    point.update(EURJPY=point["USDJPY"], GBPJPY=point["USDJPY"], EURGBP=point["EURUSD"])
    return times, px, cst, point


def synth_check(times, px):
    """Daily-return correlation of each synthetic cross with the real cross (2024+)."""
    out = {}
    for s in ("EURJPY", "GBPJPY", "EURGBP"):
        p = context.DATA / f"bars_{s}_D1.csv"
        if not p.exists():
            continue
        real = {b["time"]: b["close"] for b in context.load_bars(s, "D1")}
        idx = [i for i, t in enumerate(times) if t in real and i > 0 and times[i - 1] in real]
        a = [math.log(real[times[i]] / real[times[i - 1]]) for i in idx]
        b = [math.log(px[s][i] / px[s][i - 1]) for i in idx]
        out[s] = (len(idx), statistics.correlation(a, b), statistics.median(abs(px[s][i] / real[times[i]] - 1) for i in idx))
    return out


def swaps():
    p = context.DATA / "fx_swaps.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------------------
def vol(p, i, n=20):
    if i < n:
        return 0.0
    return sum(abs(p[k] - p[k - 1]) for k in range(i - n + 1, i + 1)) / n


def lvol(p, i, n=20):
    return sum(abs(math.log(p[k] / p[k - 1])) for k in range(i - n + 1, i + 1)) / n if i >= n else 0.0


SIGN = {(p, c): (1 if p[:3] == c else -1 if p[3:] == c else 0) for p in PAIRS for c in CURS}


def scores(px, i, L):
    sc = {}
    for c in CURS:
        v = [SIGN[(p, c)] * math.log(px[p][i] / px[p][i - L]) / (lvol(px[p], i) or 1e-9)
             for p in PAIRS if SIGN[(p, c)] != 0]
        sc[c] = sum(v) / len(v)
    return sc


def pair_of(strong, weak):
    for p in PAIRS:
        if p[:3] == strong and p[3:] == weak:
            return p, 1
        if p[:3] == weak and p[3:] == strong:
            return p, -1
    raise KeyError((strong, weak))


def run(data, fam, L, H, keep=()):
    times, px, cst, point, sw, aux = data
    out = []
    i = max(L, 250) + 1
    while i + H < len(times):
        t = times[i]
        p_ = period(t)
        if p_ is None:
            i += 1
            continue
        picks = []
        if fam == "TSM":
            for p in PAIRS:
                r = math.log(px[p][i] / px[p][i - L]) / (lvol(px[p], i) or 1e-9)
                if r != 0:
                    picks.append((p, 1 if r > 0 else -1, abs(r)))
        else:
            sc = scores(px, i, L)
            order = sorted(CURS, key=sc.get)
            strong, weak = (order[-1], order[0]) if fam == "CSM" else (order[0], order[-1])
            p, d = pair_of(strong, weak)
            picks.append((p, d, sc[order[-1]] - sc[order[0]]))
        for p, d, disp in picks:
            lab = labels(aux, fam, p, i, d, disp)
            if not all(lab[f] for f in keep):
                continue
            unit = 2 * vol(px[p], i)
            if unit <= 0:
                continue
            j = i + H
            r = (d * (px[p][j] - px[p][i]) - cst[p][i]) / unit
            out.append({"r": r, "rs": r + swap_r(sw, p, d, times, i, j, point) / unit, "utc": t, "p": p_,
                        "pair": p, "lab": lab})
        i += H
    return out


def swap_r(sw, p, d, times, i, j, point):
    s = sw.get(p)
    if not s:
        return 0.0
    rate = s["long"] if d == 1 else s["short"]
    nights = 0
    for k in range(i, j):
        wd = datetime.fromtimestamp(times[k], timezone.utc).weekday()
        nights += 3 if wd == s.get("triple", 3) - 1 else 1
    return rate * point[p] * nights


def aux_data(times, px):
    """Per pair: EMA200 of D1 closes; 20-day vol; rolling 250-day medians of vol and of dispersions."""
    aux = {"ema": {p: filters.ema(px[p], 200) for p in PAIRS}, "vol": {p: [lvol(px[p], i) for i in range(len(times))] for p in PAIRS},
           "disp": {}}
    return aux


def rolling_median(xs, i, n=250):
    w = [x for x in xs[max(0, i - n):i] if x]
    return statistics.median(w) if w else 0.0


_DISP: dict = {}


def labels(aux, fam, p, i, d, disp):
    hist = _DISP.setdefault((fam, p if fam == "TSM" else "*"), {})
    hist[i] = disp
    past = [hist[k] for k in hist if i - 250 <= k < i]
    v = aux["vol"][p]
    return {"F1": bool(past) and disp > statistics.median(past),
            "F2": d * (aux["px"][p][i] - aux["ema"][p][i]) > 0,
            "F3": v[i] < rolling_median(v, i)}


# ---------------------------------------------------------------------------
def by_year(rows):
    ys = {}
    for r in rows:
        ys.setdefault(datetime.fromtimestamp(r["utc"], timezone.utc).year, []).append(r["r"])
    return ys


def main():
    out, mean = g93.out, g93.mean
    times, px, cst, point = load()
    aux = aux_data(times, px)
    aux["px"] = px
    data = (times, px, cst, point, swaps(), aux)
    L_ = []
    out(L_, "# FX02: sức mạnh tiền tệ khung D1 — kết quả")
    out(L_)
    out(L_, "Kế hoạch: `plans/2026-10-11-fx02-currency-strength.md`. USD, EUR, GBP, JPY; 3 cặp chính thật + 3 cặp chéo "
            "tổng hợp. R = lời/lỗ sau chi phí ÷ (2 × biến động ngày 20 ngày). Ô: số lệnh / R mỗi lệnh. Chọn và chấm không swap.")
    out(L_)
    chk = synth_check(times, px)
    out(L_, "## Kiểm tra cặp chéo tổng hợp (D1, 2024–2025)")
    out(L_)
    out(L_, "| Cặp | Ngày | Tương quan lợi nhuận ngày | Lệch giá trung vị |")
    out(L_, "|---|---|---|---|")
    ok_synth = True
    for s, (n, c, dev) in chk.items():
        out(L_, f"| {s} | {n} | {c:.3f} | {dev:.3%} |")
        ok_synth = ok_synth and c >= 0.95
    out(L_)
    if not ok_synth:
        out(L_, "**Cặp chéo tổng hợp không đạt (< 0,95) → theo kế hoạch chỉ dùng 3 cặp chính.**")
        out(L_)
        global PAIRS
        PAIRS = MAJORS
    finals = []
    for fam, grid in FAMILIES.items():
        out(L_, f"## {fam} — biến thể (L ngày, giữ H ngày)")
        out(L_)
        out(L_, "| L / H | Train 2010–16 | Validate 2017–20 | Đạt? | Test 2021–25 |")
        out(L_, "|---|---|---|---|---|")
        best, best_score, rows_of = None, None, {}
        for L, H in grid:
            _DISP.clear()
            rows = run(data, fam, L, H)
            rows_of[(L, H)] = rows
            tr = [r["r"] for r in rows if r["p"] == "train"]
            va = [r["r"] for r in rows if r["p"] == "validate"]
            ok = bool(tr) and bool(va) and mean(tr) > 0 and mean(va) > 0 and len(tr) + len(va) >= 60
            if ok and (best_score is None or min(mean(tr), mean(va)) > best_score):
                best, best_score = (L, H), min(mean(tr), mean(va))
            out(L_, f"| {L} / {H} | {g93.cell(rows, 'train')} | {g93.cell(rows, 'validate')} | {'đạt' if ok else ''} | "
                    f"{g93.cell(rows, 'test')} |")
        out(L_)
        if best is None:
            out(L_, f"**{fam}: không biến thể nào đạt → dừng.**")
            out(L_)
            continue
        out(L_, f"Chọn: **L {best[0]} / H {best[1]}** (min train/validate {best_score:+.3f}).")
        out(L_)
        rows = rows_of[best]
        tv = [r for r in rows if r["p"] != "test"]
        out(L_, "| Lọc | Train: giữ / bỏ | Validate: giữ / bỏ | Giữ lệnh | Giữ lọc? |")
        out(L_, "|---|---|---|---|---|")
        kept, gaps = [], {}
        for f in FILTERS:
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
            out(L_, f"| {f} | {cells[0]} | {cells[1]} | {share:.0%} | {'**giữ**' if ok else ''} |")
        _DISP.clear()
        sel = run(data, fam, best[0], best[1], kept)
        if kept and len([r for r in sel if r["p"] != "test"]) < 30:
            kept = [max(gaps, key=gaps.get)]
            _DISP.clear()
            sel = run(data, fam, best[0], best[1], kept)
        out(L_)
        out(L_, f"Áp lọc **{', '.join(kept) or 'không'}**: train {g93.cell(sel, 'train')}, validate {g93.cell(sel, 'validate')}, "
                f"**test {g93.cell(sel, 'test')}**.")
        out(L_)
        finals.append((fam, best, kept, sel))
    out(L_, "## Kiểm tra cuối (2021–10/2025)")
    out(L_)
    out(L_, "| Họ | Biến thể + lọc | Lệnh | R/lệnh | Cận dưới 90% | Cận dưới 96,7% | Sau trừ 0,10R | Có swap (mức hiện tại) | %/năm @0,5% | DD @0,5% | Đạt? |")
    out(L_, "|---|---|---|---|---|---|---|---|---|---|---|")
    yrs = (END - TEST) / (365.25 * 86400)
    for fam, best, kept, sel in finals:
        test = sorted([r for r in sel if r["p"] == "test"], key=lambda r: r["utc"])
        rs = [r["r"] for r in test]
        if len(rs) < 2:
            out(L_, f"| {fam} | L{best[0]}/H{best[1]} {'+'.join(kept)} | {len(rs)} | | | | | | | | không |")
            continue
        m, l90, lb, mp = mean(rs), g93.lower(rs, 0.10), g93.lower(rs, 0.10 / 3), mean(rs) - PENALTY
        ok = m > 0 and l90 > 0 and mp > 0
        risk = 0.5 / (len(PAIRS) if fam == "TSM" else 1)
        out(L_, f"| {fam} | L{best[0]}/H{best[1]} {'+'.join(kept) or '—'} | {len(rs)} | {m:+.3f} | {l90:+.3f} | {lb:+.3f} | "
                f"{mp:+.3f} | {mean([r['rs'] for r in test]):+.3f} | {sum(rs) * risk / yrs:+.1f} | {g93.dd_r(rs) * risk:.1f}% | "
                f"{'**ĐẠT**' + (' (cả Bonferroni)' if lb > 0 else '') if ok else 'không'} |")
        ys = by_year(sel)
        out(L_, f"| | R theo năm | " + "; ".join(f"{y}: {len(v)} {sum(v):+.1f}" for y, v in sorted(ys.items())) + " | | | | | | | | |")
        cnt = {}
        for r in test:
            cnt[r["pair"]] = cnt.get(r["pair"], 0) + 1
        out(L_, f"| | Cặp (test) | " + ", ".join(f"{p} {n}" for p, n in sorted(cnt.items(), key=lambda x: -x[1])) + " | | | | | | | | |")
    out(L_)
    REPORT.write_text("\n".join(L_) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
