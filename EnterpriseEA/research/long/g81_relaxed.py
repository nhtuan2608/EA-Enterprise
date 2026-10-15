"""G81: S07 with relaxed strictness (EMA order, looser ADX / DI), both directions. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g81-relaxed-s07.md. MT5 data only.

  python g81_relaxed.py
"""
from __future__ import annotations

import itertools
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g81-relaxed-s07.md"
TF = {"M15": dict(comp=16, cool=8, hold=480), "M30": dict(comp=8, cool=4, hold=240), "H1": dict(comp=4, cool=2, hold=120)}
RB, KK, DI, EX = ("RB4", "RB3", "RB2"), ("K0", "K1", "K2"), ("DS", "DL"), ("X1", "X2", "X3")
KEYS = ("pre", "train", "validate", "test", "examples")
DEC3 = ("train", "validate", "test")
N_TESTS = 162
RUNS = 2000
EXAMPLES = [("Bán 23/9", -1, "2026-09-23T05:00", "2026-09-23T16:00"), ("Bán 28/9", -1, "2026-09-28T04:00", "2026-09-28T12:00"),
            ("Mua 05/8", 1, "2026-08-05T06:00", "2026-08-05T12:00"), ("Mua 19/8", 1, "2026-08-19T14:00", "2026-08-19T22:00")]

_D: dict = {}


def load(tf):
    if tf not in _D:
        g.set_tf(tf)
        g.GAP_AWARE = True
        D = g.load("XAUUSD")
        D["tf"] = tf
        D["gap"] = D["pdi"] - D["mdi"]
        D["ehi"] = np.maximum.reduce([D["E"][n] for n in (21, 55, 100, 200)])
        D["elo"] = np.minimum.reduce([D["E"][n] for n in (21, 55, 100, 200)])
        W = TF[tf]["comp"]
        n = len(D["c"])
        win = swv(D["adx"], W)
        mins = np.full(n, np.inf)
        kmin = np.zeros(n, dtype=np.int64)
        mins[W:] = win.min(1)[:n - W]
        kmin[W:] = (np.arange(len(win)) + win.argmin(1))[:n - W]
        D["minA"], D["kmin"] = mins, kmin
        _D[tf] = D
    return _D[tf]


def signals(D, d, rb, k, di):
    c, E, adx, gap = D["c"], D["E"], D["adx"], D["gap"]
    n = len(c)
    prev = np.r_[adx[0], adx[:-1]]
    prev2 = np.r_[adx[:2], adx[:-2]]
    gprev = np.r_[gap[0], gap[:-1]]
    if rb == "RB4":
        m_rb = (c > D["ehi"]) if d == 1 else (c < D["elo"])
    elif rb == "RB3":
        m_rb = ((E[21] > E[55]) & (E[55] > E[100]) & (c > E[21])) if d == 1 else ((E[21] < E[55]) & (E[55] < E[100]) & (c < E[21]))
    else:
        m_rb = ((E[21] > E[55]) & (c > E[21])) if d == 1 else ((E[21] < E[55]) & (c < E[21]))
    minA, gk = D["minA"], gap[D["kmin"]]
    if k == "K0":
        m_k = (minA <= 20) & (np.abs(gk) <= 6) & (adx > prev) & (adx - minA <= 10)
    elif k == "K1":
        m_k = (minA <= 25) & (np.abs(gk) <= 10) & (adx > prev) & (adx - minA <= 15)
    else:
        m_k = (adx > prev) & (prev > prev2) & (minA <= 30)
    m_di = (d * gap > 0) & ((d * gap > d * gprev) if di == "DS" else True)
    m = m_rb & m_k & m_di
    if d == 1:
        m &= D["h4_side"] == 1
    m[:400] = False
    m[n - 1:] = False
    return np.nonzero(m)[0]


def walk(D, i, d, ex, dist_override=None):
    o, hh, ll, c, sp, atr, adx, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"], D["adx"], D["E"]
    n = len(c)
    W, hold = TF[D["tf"]]["comp"], TF[D["tf"]]["hold"]
    e0 = i + 1
    if e0 >= n:
        return None
    entry = o[e0] + (sp[e0] if d == 1 else 0.0)
    if dist_override is None:
        a0 = i - W
        for kk in range(i, a0, -1):
            if D["t"][kk] - D["t"][kk - 1] > 6 * 3600:
                a0 = kk
                break
        anchor = (np.min(ll[a0:i + 1]) - 0.1 * atr[i]) if d == 1 else (np.max(hh[a0:i + 1]) + 0.1 * atr[i])
        dist = float(d * (entry - anchor))
        if dist > 4.0 * atr[i]:
            return None
        dist = max(dist, atr[i])
    else:
        dist = dist_override * atr[i]
    sl = entry - d * dist
    tp = entry + d * (2.0 if ex == "X2" else 8.0) * dist
    best = entry
    exit_px, x, reason = None, None, "TIME"
    for j in range(e0, min(n, e0 + hold)):
        sj = sp[j] if d == -1 else 0.0
        bh, bl, bo = hh[j] + sj, ll[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px, x, reason = (min(sl, bo) if d == 1 else max(sl, bo)), j, "SL"
            break
        if (d == 1 and bh >= tp) or (d == -1 and bl <= tp):
            exit_px, x, reason = (max(tp, bo) if d == 1 else min(tp, bo)), j, "TP"
            break
        best = max(best, hh[j]) if d == 1 else min(best, bl)
        if ex == "X2":
            out = d * (c[j] - E[21][j]) < 0
        else:
            ema = E[100] if d * (best - entry) >= 3 * dist else E[55]
            out = d * (c[j] - ema[j]) < 0
            if ex == "X3" and adx[j - 1] >= 50.0 and adx[j] < adx[j - 1]:
                out, reason = True, "ADX"
        if out and j + 1 < n:
            x = j + 1
            exit_px = o[x] + (sp[x] if d == -1 else 0.0)
            reason = reason if reason == "ADX" else "TREND"
            break
    if exit_px is None:
        x = min(n - 1, e0 + hold - 1)
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - D["comm"] / dist
    t = {"i": int(i), "d": d, "utc": int(D["utc"][i]), "r": float(r), "reason": reason, "risk": float(dist),
         "dist_atr": float(dist / atr[i]), "e0": int(e0), "x": int(x), "sp_in": float(sp[e0]), "sp_out": float(sp[x]),
         "srv_in": int(D["t"][e0]), "srv_out": int(D["t"][x])}
    t["rh"] = h.harsh(t, D)
    t["p"] = v.period(t)
    return t


def book(D, sig, d, ex):
    out, free, cool = [], 0, TF[D["tf"]]["cool"]
    for i in sig:
        if i < free:
            continue
        t = walk(D, int(i), d, ex)
        if t is None:
            continue
        out.append(t)
        free = t["x"] + 1 + cool
    return out


def per(trs):
    return {q: g.stats([t["rh"] for t in trs if t["p"] == q]) for q in KEYS}


def tv(ps):
    n = ps["train"]["n"] + ps["validate"]["n"]
    return n, ((ps["train"]["total"] + ps["validate"]["total"]) / n if n else 0.0)


def rand_job(arg):
    tf, d, ex, rows, seed, runs = arg
    D = load(tf)
    rng = np.random.default_rng(seed)
    n = len(D["c"])
    pools = {}
    for name in DEC3:
        a, z = next((x[1], x[2]) for x in g.PERIODS if x[0] == name)
        idx = np.nonzero((D["utc"] >= a) & (D["utc"] < z))[0]
        pools[name] = idx[(idx > 400) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = [walk(D, int(rng.choice(pools[t["p"]])), d, ex, t["dist_atr"]) for t in rows]
        means.append(float(np.mean([x["rh"] for x in rs if x])))
    return means


def p_random(tf, d, ex, trs):
    rows = [{"p": t["p"], "dist_atr": t["dist_atr"]} for t in trs if t["p"] in DEC3]
    real = float(np.mean([t["rh"] for t in trs if t["p"] in DEC3]))
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(tf, d, ex, rows, 8100 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def examples(trs, d, bar_sec):
    out = []
    for name, dd, a, z in EXAMPLES:
        if dd != d:
            continue
        a = datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        z = datetime.fromisoformat(z).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        hit = [t for t in trs if a <= t["utc"] <= z]
        if hit:
            t = hit[0]
            vn = datetime.fromtimestamp(t["utc"] + bar_sec + 7 * 3600, timezone.utc)
            out.append(f"{name}: vào {vn:%d/%m %H:%M} VN, {t['rh']:+.2f}R ({t['reason']})")
        else:
            out.append(f"{name}: không vào")
    return "; ".join(out)


def dd90(trs):
    x = [{"utc": t["utc"], "r": t["rh"]} for t in trs if t["p"] in DEC3]
    return h.dd_p90(x, 0.015) if len(x) >= 20 else float("nan")


def neighbours(key):
    tf, rb, k, di, ex = key
    out = []
    for arr, pos, idx in ((RB, 1, RB.index(rb)), (KK, 2, KK.index(k))):
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(arr):
                kk = list(key)
                kk[pos] = arr[j]
                out.append(tuple(kk))
    return out


def main():
    L = ["# G81: S07 nới độ khắt khe — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g81-relaxed-s07.md`. XAUUSD, chi phí khắt khe G68. Ô: số lệnh / R mỗi lệnh. "
         "Mua luôn có lọc H4 trên EMA200 H4; bán không lọc khung lớn. Bộ \"RB4 / K0 / DS / X1\" = S07 gốc.", ""]
    for d, dn in ((-1, "Bán"), (1, "Mua")):
        grid, books = {}, {}
        for tf in TF:
            D = load(tf)
            for rb, k, di in itertools.product(RB, KK, DI):
                sig = signals(D, d, rb, k, di)
                for ex in EX:
                    trs = book(D, sig, d, ex)
                    grid[(tf, rb, k, di, ex)] = per(trs)
                    books[(tf, rb, k, di, ex)] = trs
            sys.stdout.buffer.write(f"{dn} {tf}\n".encode()); sys.stdout.flush()
        L += [f"## {dn}", "", "Mười bộ đứng đầu theo R/lệnh train + validate (≥ 100 lệnh):", "",
              "| Khung | Dải EMA | Nén/ADX | DI | Thoát | " + " | ".join(v.NAMES[q] for q in KEYS) + " | Train+val |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        ranked = sorted([k for k in grid if tv(grid[k])[0] >= 100], key=lambda k: tv(grid[k])[1], reverse=True)
        cell = lambda s: f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"
        for key in ranked[:10]:
            L.append("| " + " | ".join(key) + " | " + " | ".join(cell(grid[key][q]) for q in KEYS) +
                     f" | {tv(grid[key])[0]} / {tv(grid[key])[1]:+.3f} |")
        L += ["", "S07 gốc (RB4 / K0 / DS / X1) và các bản nới cùng thoát X1, theo khung:", "",
              "| Khung | Dải EMA | Nén/ADX | DI | " + " | ".join(v.NAMES[q] for q in KEYS) + " | Train+val |", "|---|---|---|---|---|---|---|---|---|---|"]
        for tf in TF:
            for rb, k in (("RB4", "K0"), ("RB3", "K0"), ("RB3", "K1"), ("RB3", "K2"), ("RB2", "K2")):
                for di in DI:
                    key = (tf, rb, k, di, "X1")
                    L.append("| " + " | ".join(key[:4]) + " | " + " | ".join(cell(grid[key][q]) for q in KEYS) +
                             f" | {tv(grid[key])[0]} / {tv(grid[key])[1]:+.3f} |")
        cands = [k for k in grid if grid[k]["train"]["n"] and grid[k]["validate"]["n"] and grid[k]["train"]["exp"] > 0
                 and grid[k]["validate"]["exp"] > 0 and tv(grid[k])[0] >= 100]
        L += ["", f"Ứng viên (dương train và validate, ≥ 100 lệnh): {len(cands)} / 162.", ""]
        if cands:
            pick = max(cands, key=lambda k: tv(grid[k])[1])
            tf, rb, k, di, ex = pick
            ps, trs = grid[pick], books[pick]
            rm, p = p_random(tf, d, ex, trs)
            nb = neighbours(pick)
            nb_ok = [grid[x]["train"]["n"] and grid[x]["validate"]["n"] and grid[x]["train"]["exp"] > 0 and grid[x]["validate"]["exp"] > 0
                     for x in nb]
            checks = {"test > 0": ps["test"]["n"] and ps["test"]["exp"] > 0,
                      "2018–2021 ≥ 0 (nếu có)": (not ps["pre"]["n"]) or ps["pre"]["exp"] >= 0,
                      f"thắng ngẫu nhiên p < 0,05/162 (p = {p:.4f}, TB ngẫu nhiên {rm:+.3f})": p < 0.05 / N_TESTS,
                      f"lân cận dương train + validate ≥ 60% ({sum(nb_ok)}/{len(nb)})": (sum(nb_ok) / max(len(nb), 1)) >= 0.6}
            if d == 1:
                base = books[("M30", "RB4", "K0", "DS", "X1")]
                sel = [t for t in trs if t["p"] in DEC3]
                b = [t for t in base if t["p"] in DEC3]
                mb, ms = np.mean([t["rh"] for t in b]), np.mean([t["rh"] for t in sel])
                tb, ts_ = sum(t["rh"] for t in b), sum(t["rh"] for t in sel)
                checks[f"hơn S07 M30 (R/lệnh {ms:+.3f} vs {mb:+.3f}, tổng {ts_:+.1f} vs {tb:+.1f}, DD p90 {dd90(trs):.0%} vs {dd90(base):.0%})"] = \
                    ms >= mb and ts_ >= tb and dd90(trs) <= dd90(base) + 0.02
            ok = all(checks.values())
            L += [f"Chọn: **{' / '.join(pick)}** — train + validate {tv(ps)[0]} lệnh / {tv(ps)[1]:+.3f}R; "
                  f"test {cell(ps['test'])}; 2018–2021 {cell(ps['pre'])}; DD p90 {dd90(trs):.0%}."]
            L += [f"- {c}: {'đạt' if x else 'KHÔNG'}" for c, x in checks.items()]
            L += [f"- Lân cận: " + "; ".join(f"{'/'.join(x[1:3])} {cell(grid[x]['train'])} · {cell(grid[x]['validate'])}" for x in nb)]
            s07 = set(t["i"] for t in books[(tf, "RB4", "K0", "DS", ex)])
            L += [f"- Lệnh trùng với S07 gốc cùng khung/thoát: {sum(1 for t in trs if t['i'] in s07)}/{len(trs)}",
                  f"- Ví dụ: {examples(trs, d, {'M15': 900, 'M30': 1800, 'H1': 3600}[tf])}",
                  f"- S07 gốc cùng khung: {examples(books[(tf, 'RB4', 'K0', 'DS', 'X1')], d, {'M15': 900, 'M30': 1800, 'H1': 3600}[tf])}",
                  "", f"**Kết luận theo luật ({dn}): {'ĐẠT' if ok else 'không đạt'}.**", ""]
        else:
            L += [f"**Kết luận theo luật ({dn}): không bộ nào đủ điều kiện.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
