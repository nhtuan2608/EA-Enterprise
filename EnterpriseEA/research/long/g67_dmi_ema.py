"""G67: compression -> expansion on DMI + EMA ribbon, XAUUSD M15. Pre-registered plan:
docs/superpowers/plans/2026-10-09-g67-dmi-ema-compression.md. MT5 data only (g67_data.py).

  python g67_dmi_ema.py

Steps (as registered): 9 exits (trend exit x far TP) chosen on train; blocks B1..B7 tried one at a time
against that base; a block is kept when it raises R/trade in train and validate with >= 50% of the trades;
final rule = base + best kept block (+ one 2-block combination if two are kept). Checks on the final rule:
three periods positive, random entries p < 0.05/9, costs x2 + 0.1R, other symbols, by year, the
07/2026.. examples period reported apart.
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "m15v"
OUT = HERE / "results"
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-09-g67-dmi-ema-compression.md"

POINT = {"XAUUSD": 0.01, "XAGUSD": 0.001, "USDJPY": 0.001, "EURUSD": 0.00001, "GBPUSD": 0.00001, "BTCUSD": 0.01}
COMMISSION = {"XAUUSD": 0.06, "XAGUSD": 0.0012, "USDJPY": 0.009, "EURUSD": 0.00006, "GBPUSD": 0.00006, "BTCUSD": 0.0}
OTHERS = ["XAGUSD", "USDJPY", "BTCUSD", "EURUSD", "GBPUSD"]


def ts(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


PERIODS = [("train", ts(2021, 7, 20), ts(2024, 1, 1)), ("validate", ts(2024, 1, 1), ts(2025, 7, 1)),
           ("test", ts(2025, 7, 1), ts(2026, 7, 1)), ("examples", ts(2026, 7, 1), ts(2030, 1, 1))]
DECIDE = ("train", "validate", "test")

COMP_BARS, ADX_LOW, DI_GAP, ADX_RISE = 16, 20.0, 6.0, 10.0
STOP_BUF, STOP_MIN, STOP_MAX, COOLDOWN, MAX_HOLD = 0.1, 1.0, 4.0, 8, 480
EXITS = [(e, tp) for e in ("E1", "E2", "E3") for tp in (5.0, 8.0, None)]
BLOCKS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]
BLOCK_NAMES = {"B1": "giờ mở phiên (00–03, 07–09, 12–15 UTC)", "B2": "nến đóng :00 / :30",
               "B3": "nén có volume thấp", "B4": "cắt sớm khi 4 nến đầu volume < 0,9",
               "B5": "dời SL hòa vốn ở +1R", "B6": "cùng chiều EMA200 H4", "B7": "bỏ khi spread > 2× trung vị"}
EXIT_NAMES = {"E1": "đóng ngược EMA21 khi ADX đã giảm ≥ 5 từ đỉnh", "E2": "đóng ngược EMA55",
              "E3": "trail 3 ATR"}


# ---------------------------------------------------------------------------
# data and indicators
# ---------------------------------------------------------------------------
def us_dst(utc: int) -> bool:
    y = datetime.fromtimestamp(utc, timezone.utc).year

    def nth_sunday(month, nth):
        first = datetime(y, month, 1, tzinfo=timezone.utc)
        off = (6 - first.weekday()) % 7
        return int(first.timestamp()) + (off + (nth - 1) * 7) * 86400

    return nth_sunday(3, 2) + 7 * 3600 <= utc < nth_sunday(11, 1) + 6 * 3600


def rma(x, n):
    out = np.empty_like(x)
    out[0] = x[0]
    a = 1.0 / n
    for i in range(1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def ema(x, n):
    out = np.empty_like(x)
    out[0] = x[0]
    a = 2.0 / (n + 1)
    for i in range(1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


_CACHE: dict = {}


def load(symbol: str) -> dict:
    if symbol in _CACHE:
        return _CACHE[symbol]
    rows = list(csv.DictReader(open(DATA / f"{symbol}.csv")))
    t = np.array([int(r["time"]) for r in rows], dtype=np.int64)
    o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
    v = np.array([float(r["tickvol"]) for r in rows])
    utc = np.array([x - (10800 if us_dst(x - 7200) else 7200) for x in t], dtype=np.int64)
    sp_raw = np.array([float(r["spread"]) for r in rows]) * POINT[symbol]
    recent = sp_raw[(utc >= ts(2024, 1, 1)) & (utc < ts(2026, 1, 1))]
    sp_med = float(np.median(recent)) if len(recent) else float(np.median(sp_raw))
    sp = np.maximum(sp_raw, sp_med)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    up = h - np.concatenate([[h[0]], h[:-1]])
    dn = np.concatenate([[l[0]], l[:-1]]) - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    trs, pdms, mdms = rma(tr, 14), rma(pdm, 14), rma(mdm, 14)
    pdi, mdi = 100 * pdms / trs, 100 * mdms / trs
    dx = 100 * abs(pdi - mdi) / np.maximum(pdi + mdi, 1e-9)
    adx = rma(dx, 14)
    atr = trs
    E = {n: ema(c, n) for n in (21, 55, 100, 200)}
    # tick volume vs the same 15-minute slot over the previous 20 days
    slot_hist = defaultdict(list)
    rv = np.full(len(t), np.nan)
    for i in range(len(t)):
        s = int(t[i] % 86400)
        hist = slot_hist[s]
        if len(hist) >= 10:
            rv[i] = v[i] / max(1.0, statistics.fmean(hist[-20:]))
        hist.append(v[i])
    # H4 close and EMA200 of the last completed H4 bar (server-time 4h buckets)
    bucket = t // 14400
    h4_close, h4_bucket = [], []
    for i in range(len(t)):
        if i + 1 == len(t) or bucket[i + 1] != bucket[i]:
            h4_close.append(c[i]); h4_bucket.append(bucket[i])
    h4_ema = ema(np.array(h4_close), 200)
    pos = {b: k for k, b in enumerate(h4_bucket)}
    h4_side = np.zeros(len(t))
    for i in range(len(t)):
        k = pos.get(bucket[i], 0) - 1
        if k >= 200:
            h4_side[i] = np.sign(h4_close[k] - h4_ema[k])
    d = dict(sym=symbol, t=t, utc=utc, o=o, h=h, l=l, c=c, v=v, rv=rv, sp=sp, sp_med=sp_med, atr=atr, adx=adx,
             pdi=pdi, mdi=mdi, E=E, h4_side=h4_side, comm=COMMISSION[symbol])
    _CACHE[symbol] = d
    return d


def period_of(utc: int) -> str:
    for name, a, z in PERIODS:
        if a <= utc < z:
            return name
    return "none"


# ---------------------------------------------------------------------------
# signals and trades
# ---------------------------------------------------------------------------
def signals(D: dict) -> list[tuple[int, int]]:
    """(bar index, direction) of every bar that meets the four base conditions."""
    adx, pdi, mdi, c, E = D["adx"], D["pdi"], D["mdi"], D["c"], D["E"]
    hi = np.maximum.reduce([E[21], E[55], E[100], E[200]])
    lo = np.minimum.reduce([E[21], E[55], E[100], E[200]])
    gap = pdi - mdi
    out = []
    for i in range(400, len(c) - 1):
        w = slice(i - COMP_BARS, i)
        k = i - COMP_BARS + int(np.argmin(adx[w]))
        if adx[k] > ADX_LOW or abs(gap[k]) > DI_GAP:
            continue
        if not (adx[i] > adx[i - 1] and adx[i] - adx[k] <= ADX_RISE):
            continue
        if gap[i] > 0 and gap[i] > gap[i - 1] and c[i] > hi[i]:
            out.append((i, 1))
        elif gap[i] < 0 and gap[i] < gap[i - 1] and c[i] < lo[i]:
            out.append((i, -1))
    return out


def block_ok(D, i, d, block) -> bool:
    if block == "B1":
        hr = ((D["utc"][i] + 900) // 3600) % 24
        return hr < 3 or 7 <= hr < 9 or 12 <= hr < 15
    if block == "B2":
        return (D["t"][i] + 900) % 1800 == 0
    if block == "B3":
        r = D["rv"][i - COMP_BARS:i]
        r = r[~np.isnan(r)]
        return len(r) > 0 and float(np.mean(r)) < 1.0
    if block == "B6":
        return D["h4_side"][i] == d
    if block == "B7":
        return D["sp"][i] <= 2.0 * D["sp_med"]
    return True


def walk(D, i, d, exit_rule, tp_r, block, dist_override=None):
    """One trade from the signal at bar i; None when the stop is outside 1..4 ATR."""
    o, h, l, c, sp, atr, adx, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"], D["adx"], D["E"]
    n = len(c)
    e0 = i + 1
    if e0 >= n:
        return None
    entry = o[e0] + (sp[e0] if d == 1 else 0.0)
    if dist_override is None:
        anchor = (np.min(l[i - COMP_BARS:i + 1]) - STOP_BUF * atr[i]) if d == 1 else \
                 (np.max(h[i - COMP_BARS:i + 1]) + STOP_BUF * atr[i])
        dist = d * (entry - anchor)
        if dist > STOP_MAX * atr[i]:
            return None
        dist = max(dist, STOP_MIN * atr[i])
    else:
        dist = dist_override * atr[i]
    sl = entry - d * dist
    tp = entry + d * tp_r * dist if tp_r else None
    peak_adx = adx[i]
    best = entry
    exit_px, x, reason = None, None, "TIME"
    for j in range(e0, min(n, e0 + MAX_HOLD)):
        sj = sp[j] if d == -1 else 0.0          # a short closes on the ask
        bh, bl, bo = h[j] + sj, l[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px = min(sl, bo) if d == 1 else max(sl, bo)
            x, reason = j, "SL"
            break
        if tp is not None and ((d == 1 and bh >= tp) or (d == -1 and bl <= tp)):
            exit_px = max(tp, bo) if d == 1 else min(tp, bo)
            x, reason = j, "TP"
            break
        cj = c[j] + sj
        best = max(best, h[j]) if d == 1 else min(best, l[j] + sj)
        peak_adx = max(peak_adx, adx[j])
        out = False
        if exit_rule == "E1":
            out = d * (c[j] - E[21][j]) < 0 and adx[j] <= peak_adx - 5
        elif exit_rule == "E2":
            out = d * (c[j] - E[55][j]) < 0
        elif exit_rule == "E3":
            trail = best - d * 3.0 * atr[j]
            if d * (trail - sl) > 0:
                sl = trail
        if block == "B5" and d * (best - entry) >= dist and d * (entry - sl) > 0:
            sl = entry
        if block == "B4" and j == e0 + 3:
            r = D["rv"][e0:e0 + 4]
            r = r[~np.isnan(r)]
            if len(r) and float(np.mean(r)) < 0.9:
                out, reason = True, "B4"
        if out and j + 1 < n:
            x = j + 1
            exit_px = o[x] + (sp[x] if d == -1 else 0.0)
            reason = reason if reason == "B4" else "TREND"
            break
    if exit_px is None:
        x = min(n - 1, e0 + MAX_HOLD - 1)
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - D["comm"] / dist
    return {"sym": D["sym"], "i": i, "d": d, "utc": int(D["utc"][i]), "r": float(r), "reason": reason,
            "hold_h": (x - e0 + 1) * 0.25, "dist_atr": float(dist / atr[i]), "risk": float(dist),
            "cost_r": float((sp[e0] + D["comm"]) / dist)}


def trades(symbol, exit_rule, tp_r, block=None, sigs=None):
    D = load(symbol)
    sigs = signals(D) if sigs is None else sigs
    out, free = [], 0
    for i, d in sigs:
        if i < free:
            continue
        if block and not block_ok(D, i, d, block):
            continue
        tr = walk(D, i, d, exit_rule, tp_r, block)
        if tr is None:
            continue
        out.append(tr)
        free = i + 1 + int(tr["hold_h"] * 4) + COOLDOWN
    return out


def stats(rs: list[float]) -> dict:
    if not rs:
        return {"n": 0, "exp": 0.0, "win": 0.0, "avg_win": 0.0, "dd": 0.0, "total": 0.0}
    eq = np.cumsum(rs)
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])))
    wins = [x for x in rs if x > 0]
    return {"n": len(rs), "exp": float(np.mean(rs)), "win": len(wins) / len(rs),
            "avg_win": float(np.mean(wins)) if wins else 0.0, "dd": dd, "total": float(np.sum(rs))}


def by_period(rows):
    return {p: stats([t["r"] for t in rows if period_of(t["utc"]) == p]) for p, _, _ in PERIODS}


def fmt(s):
    return f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "0 / —"


# ---------------------------------------------------------------------------
# random entries: same count per period, same directions, same stop in ATR, same exit
# ---------------------------------------------------------------------------
def random_job(job):
    symbol, rows, exit_rule, tp_r, block, seed, runs = job
    D = load(symbol)
    rng = np.random.default_rng(seed)
    n = len(D["c"])
    pool_idx = {}
    for name, a, z in PERIODS:
        idx = np.nonzero((D["utc"] >= a) & (D["utc"] < z))[0]
        pool_idx[name] = idx[(idx > 400) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            i = int(rng.choice(pool_idx[period_of(t["utc"])]))
            tr = walk(D, i, t["d"], exit_rule, tp_r, block if block in ("B4", "B5") else None, t["dist_atr"])
            if tr:
                rs.append(tr["r"])
        means.append(float(np.mean(rs)))
    return means


# ---------------------------------------------------------------------------
def main():
    lines = ["# G67: Nén → bung theo DMI + dải EMA (XAUUSD M15) — kết quả", "",
             "Kế hoạch đăng ký trước: `plans/2026-10-09-g67-dmi-ema-compression.md`. Chỉ dữ liệu MT5. "
             "Mỗi ô: số lệnh / R trung bình mỗi lệnh (đã trừ spread và commission).", ""]
    D = load("XAUUSD")
    sigs = signals(D)

    # 1. exits, chosen on train
    lines += ["## 1. Cách thoát (chọn trên train)", "",
              "| Thoát | TP | Train | Validate | Test | Ví dụ 07/2026– |", "|---|---|---|---|---|---|"]
    exit_res = []
    for e, tp in EXITS:
        rows = trades("XAUUSD", e, tp, None, sigs)
        bp = by_period(rows)
        exit_res.append(((e, tp), rows, bp))
        lines.append(f"| {e}: {EXIT_NAMES[e]} | {f'{tp:g}R' if tp else 'không'} | {fmt(bp['train'])} | "
                     f"{fmt(bp['validate'])} | {fmt(bp['test'])} | {fmt(bp['examples'])} |")
    (e_best, tp_best), base_rows, base_bp = max(exit_res, key=lambda x: x[2]["train"]["exp"])
    lines += ["", f"Chọn: **{e_best}** ({EXIT_NAMES[e_best]}), TP {f'{tp_best:g}R' if tp_best else 'không'}.", ""]

    # 2. blocks one at a time
    lines += ["## 2. Bộ chặn rủi ro — thử từng cái một", "",
              "| Bộ chặn | Train | Validate | Test | Giữ lệnh | Kết luận |", "|---|---|---|---|---|---|",
              f"| (gốc) | {fmt(base_bp['train'])} | {fmt(base_bp['validate'])} | {fmt(base_bp['test'])} | 100% | |"]
    kept = []
    block_rows = {}
    for b in BLOCKS:
        rows = trades("XAUUSD", e_best, tp_best, b, sigs)
        bp = by_period(rows)
        block_rows[b] = (rows, bp)
        share = len([t for t in rows if period_of(t["utc"]) in ("train", "validate")]) / max(
            1, base_bp["train"]["n"] + base_bp["validate"]["n"])
        keep = (bp["train"]["exp"] > base_bp["train"]["exp"] and bp["validate"]["exp"] > base_bp["validate"]["exp"]
                and share >= 0.5)
        if keep:
            kept.append((b, bp["train"]["exp"]))
        lines.append(f"| {b}: {BLOCK_NAMES[b]} | {fmt(bp['train'])} | {fmt(bp['validate'])} | {fmt(bp['test'])} | "
                     f"{share:.0%} | {'giữ' if keep else 'bỏ'} |")
    kept.sort(key=lambda x: -x[1])
    final_block = kept[0][0] if kept else None
    final_rows = block_rows[final_block][0] if final_block else base_rows
    combo_note = ""
    if len(kept) >= 2:
        b1, b2 = kept[0][0], kept[1][0]
        filt = [b for b in (b1, b2) if b not in ("B4", "B5")]
        mng = [b for b in (b1, b2) if b in ("B4", "B5")]
        if len(mng) <= 1:
            sig2 = [(i, d) for i, d in sigs if all(block_ok(D, i, d, b) for b in filt)]
            rows2 = trades("XAUUSD", e_best, tp_best, mng[0] if mng else None, sig2)
            bp2 = by_period(rows2)
            better = bp2["train"]["exp"] > block_rows[b1][1]["train"]["exp"] and \
                bp2["validate"]["exp"] > block_rows[b1][1]["validate"]["exp"]
            combo_note = (f"Tổ hợp {b1}+{b2}: train {fmt(bp2['train'])}, validate {fmt(bp2['validate'])}, "
                          f"test {fmt(bp2['test'])} → {'dùng tổ hợp' if better else 'không tốt hơn ' + b1}.")
            if better:
                final_block, final_rows = f"{b1}+{b2}", rows2
    lines += ["", f"Bộ chặn được chọn: **{final_block or 'không có'}**. {combo_note}", ""]

    # 3. checks on the final rule
    bp = by_period(final_rows)
    decide = [t for t in final_rows if period_of(t["utc"]) in DECIDE]
    real = float(np.mean([t["r"] for t in decide])) if decide else 0.0
    rand_block = final_block if final_block in ("B4", "B5") else None
    jobs = [("XAUUSD", decide, e_best, tp_best, rand_block, 6700 + k, 20) for k in range(10)]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(random_job, jobs) for m in ch]
    p_rand = float(np.mean(np.array(sims) >= real))
    stress = [t["r"] - t["cost_r"] - 0.1 for t in decide]
    passed = {
        "ba kỳ dương": all(bp[k]["exp"] > 0 and bp[k]["n"] > 0 for k in DECIDE),
        f"ngẫu nhiên p < {0.05 / 9:.4f}": p_rand < 0.05 / 9,
        "phí ×2 + 0,1R > 0": float(np.mean(stress)) > 0 if stress else False,
    }
    lines += ["## 3. Quy tắc cuối", "", "| Kỳ | Lệnh | R/lệnh | Thắng | R TB lệnh thắng | Sụt giảm max (R) | Tổng R |",
              "|---|---|---|---|---|---|---|"]
    for k, s in bp.items():
        lines.append(f"| {k} | {s['n']} | {s['exp']:+.3f} | {s['win']:.0%} | {s['avg_win']:+.2f} | {s['dd']:.1f} | "
                     f"{s['total']:+.1f} |")
    holds = [t["hold_h"] for t in decide]
    reasons = defaultdict(int)
    for t in decide:
        reasons[t["reason"]] += 1
    lines += ["", f"- Ngẫu nhiên (200 lần, cùng chiều/khoảng dừng/cách thoát): TB {np.mean(sims):+.3f}R, p = {p_rand:.3f}.",
              f"- Phí ×2 + trượt 0,1R: {np.mean(stress):+.3f}R/lệnh." if stress else "- Phí ×2: không có lệnh.",
              f"- Giữ lệnh: trung vị {np.median(holds):.1f} giờ, 90% ≤ {np.percentile(holds, 90):.1f} giờ." if holds else "",
              f"- Lý do thoát: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())), ""]
    years = defaultdict(list)
    for t in final_rows:
        years[datetime.fromtimestamp(t["utc"], timezone.utc).year].append(t["r"])
    lines += ["Theo năm: " + ", ".join(f"{y} {len(v)} lệnh {np.mean(v):+.2f}R" for y, v in sorted(years.items())), ""]
    by_dir = {d: stats([t["r"] for t in decide if t["d"] == d]) for d in (1, -1)}
    lines += [f"Theo chiều: mua {fmt(by_dir[1])}, bán {fmt(by_dir[-1])}.", ""]

    # other symbols, same rule
    lines += ["## 4. Các symbol khác (cùng quy tắc, không chỉnh)", "", "| Symbol | Train | Validate | Test | Ví dụ |",
              "|---|---|---|---|---|"]
    other_means = []
    for s in OTHERS:
        if not (DATA / f"{s}.csv").exists():
            continue
        Ds = load(s)
        sg = signals(Ds)
        if final_block and "+" not in str(final_block) and final_block not in ("B4", "B5"):
            sg = [(i, d) for i, d in sg if block_ok(Ds, i, d, final_block)]
            rows = trades(s, e_best, tp_best, None, sg)
        elif final_block and "+" in str(final_block):
            parts = final_block.split("+")
            sg = [(i, d) for i, d in sg if all(block_ok(Ds, i, d, b) for b in parts if b not in ("B4", "B5"))]
            mng = [b for b in parts if b in ("B4", "B5")]
            rows = trades(s, e_best, tp_best, mng[0] if mng else None, sg)
        else:
            rows = trades(s, e_best, tp_best, final_block, sg)
        b = by_period(rows)
        dec = [t["r"] for t in rows if period_of(t["utc"]) in DECIDE]
        if dec:
            other_means.append(float(np.mean(dec)))
        lines.append(f"| {s} | {fmt(b['train'])} | {fmt(b['validate'])} | {fmt(b['test'])} | {fmt(b['examples'])} |")
    passed["symbol khác không âm TB"] = bool(other_means) and float(np.mean(other_means)) >= 0
    lines += ["", "## 5. Tiêu chí", ""] + [f"- {k}: {'ĐẠT' if v else 'KHÔNG ĐẠT'}" for k, v in passed.items()]
    lines += ["", f"**Kết luận: {'ĐẠT tất cả tiêu chí' if all(passed.values()) else 'KHÔNG đạt đủ tiêu chí'}.**", ""]

    # the four examples
    ex = [t for t in final_rows if period_of(t["utc"]) == "examples"]
    lines += ["## 6. Các lệnh trong kỳ ví dụ (07/2026–)", "", "| Giờ tín hiệu (VN) | Chiều | R | Thoát | Giữ (giờ) |",
              "|---|---|---|---|---|"]
    for t in ex:
        vn = datetime.fromtimestamp(t["utc"] + 900 + 7 * 3600, timezone.utc)
        lines.append(f"| {vn:%d/%m %H:%M} | {'mua' if t['d'] == 1 else 'bán'} | {t['r']:+.2f} | {t['reason']} | {t['hold_h']:.1f} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
