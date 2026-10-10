"""G80: a dedicated sell setup on small timeframes (XAUUSD). Pre-registered plan:
docs/superpowers/plans/2026-10-10-g80-sell-scalp.md. MT5 data only.

  python g80_sell_scalp.py
"""
from __future__ import annotations

import itertools
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g69_two_sided as v  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g80-sell-scalp.md"
TF = {"M15": dict(comp=16, cool=8, hold=480), "M30": dict(comp=8, cool=4, hold=240), "M5": dict(comp=48, cool=24, hold=1440)}
SEC = {"M5": 300, "M15": 900, "M30": 1800}
CTX, LOC, TRIG, EXIT = ("C0", "C1", "C2", "C3"), ("L0", "LH"), ("TC", "TR"), ("X1", "X2", "X3")
KEYS = ("pre", "train", "validate", "test", "examples")
DECIDE = ("train", "validate")
PRIOR = 48
N_TESTS = 96
RUNS = 2000
D_SELL = -1

_DATA: dict = {}


def load(tf):
    """Entry bars with the H1 context of the last closed H1 bar (EMA21, EMA55, close, EMA55 three bars back)."""
    if tf in _DATA:
        return _DATA[tf]
    g.set_tf("H1")
    H = g.load("XAUUSD")
    g.set_tf(tf)
    c = TF[tf]
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = c["comp"], c["cool"], c["hold"]
    g.ADX_LOW, g.DI_GAP, g.ADX_RISE, g.GAP_AWARE = 20.0, 6.0, 10.0, True
    D = g.load("XAUUSD")
    close = D["t"] + SEC[tf]
    hclose = H["t"] + 3600
    k = np.searchsorted(hclose, close, side="right") - 1
    ok = k >= 3
    kk = np.clip(k, 3, None)
    D["c1"] = ok & (H["E"][21][kk] < H["E"][55][kk])
    D["c2"] = ok & (H["c"][kk] < H["E"][55][kk]) & (H["E"][55][kk] < H["E"][55][kk - 3])
    D["c3"] = D["h4_side"] == -1
    D["ehi"] = np.maximum.reduce([D["E"][n] for n in (21, 55, 100, 200)])
    D["elo"] = np.minimum.reduce([D["E"][n] for n in (21, 55, 100, 200)])
    D["tf"] = tf
    _DATA[tf] = D
    return D


def prior_high(D, i, W):
    w0 = i - W
    seg = D["h"][max(0, w0 - PRIOR):w0]
    return float(seg.max()) if len(seg) else np.nan


def triggers(D, trig):
    """Sell signal bars of one entry kind."""
    W = TF[D["tf"]]["comp"]
    if trig == "TC":
        g.COMP_BARS = W
        return [i for i, d in g.signals(D) if d == D_SELL]
    adx, pdi, mdi, c, hh, atr = D["adx"], D["pdi"], D["mdi"], D["c"], D["h"], D["atr"]
    out = []
    for i in range(400, len(c) - 1):
        if not c[i] < D["elo"][i]:
            continue
        if not (mdi[i] > pdi[i] and (mdi[i - 1] <= pdi[i - 1] or mdi[i - 2] <= pdi[i - 2])):
            continue
        seg = slice(i - W, i)
        k = i - W + int(np.argmax(adx[seg]))
        if adx[k] < 25.0 or pdi[k] <= mdi[k] or adx[i] >= adx[k] - 3.0:
            continue
        P = prior_high(D, i, W)
        if np.isnan(P) or hh[i - W:i + 1].max() < P - 0.5 * atr[i]:
            continue
        out.append(i)
    return out


def ctx_ok(D, i, ctx):
    return True if ctx == "C0" else bool(D[{"C1": "c1", "C2": "c2", "C3": "c3"}[ctx]][i])


def loc_ok(D, i, loc):
    if loc == "L0":
        return True
    W = TF[D["tf"]]["comp"]
    P = prior_high(D, i, W)
    T = float(D["h"][i - W:i + 1].max())
    return (not np.isnan(P)) and P - D["atr"][i] <= T <= P


def walk(D, i, exit_rule, dist_override=None, e_override=None):
    """Sell from the next open after bar i (or from e_override); stop as S07 (window high, gap-aware, 1-4 ATR)."""
    o, hh, ll, c, sp, atr, adx, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["atr"], D["adx"], D["E"]
    n = len(c)
    W, hold = TF[D["tf"]]["comp"], TF[D["tf"]]["hold"]
    e0 = i + 1 if e_override is None else e_override
    if e0 >= n:
        return None
    entry = o[e0]
    if dist_override is None:
        a0 = i - W
        for k in range(i, a0, -1):
            if D["t"][k] - D["t"][k - 1] > 6 * 3600:
                a0 = k
                break
        dist = float(np.max(hh[a0:i + 1]) + 0.1 * atr[i] - entry)
        if dist > 4.0 * atr[i]:
            return None
        dist = max(dist, atr[i])
    else:
        dist = dist_override * atr[i]
    sl = entry + dist
    tp = entry - (2.0 if exit_rule == "X2" else 8.0) * dist
    best = entry
    exit_px, x, reason = None, None, "TIME"
    for j in range(e0, min(n, e0 + hold)):
        s = sp[j]
        bh, bl, bo = hh[j] + s, ll[j] + s, o[j] + s
        if bh >= sl:
            exit_px, x, reason = max(sl, bo), j, "SL"
            break
        if bl <= tp:
            exit_px, x, reason = min(tp, bo), j, "TP"
            break
        best = min(best, bl)
        if exit_rule == "X2":
            out = c[j] > E[21][j]
        else:
            ema = E[100] if (entry - best) >= 3 * dist else E[55]
            out = c[j] > ema[j]
            if exit_rule == "X3" and adx[j - 1] >= 50.0 and adx[j] < adx[j - 1]:
                out, reason = True, "ADX"
        if out and j + 1 < n:
            x = j + 1
            exit_px = o[x] + sp[x]
            reason = reason if reason == "ADX" else "TREND"
            break
    if exit_px is None:
        x = min(n - 1, e0 + hold - 1)
        exit_px = c[x] + sp[x]
    r = (entry - exit_px) / dist - D["comm"] / dist
    t = {"i": int(i), "d": D_SELL, "utc": int(D["utc"][i]), "r": float(r), "reason": reason, "risk": float(dist),
         "dist_atr": float(dist / atr[i]), "e0": int(e0), "x": int(x), "sp_in": float(sp[e0]), "sp_out": float(sp[x]),
         "srv_in": int(D["t"][e0]), "srv_out": int(D["t"][x])}
    t["rh"] = h.harsh(t, D)
    t["p"] = v.period(t)
    return t


def book(D, sig, exit_rule):
    out, free = [], 0
    cool = TF[D["tf"]]["cool"]
    for i in sig:
        if i < free:
            continue
        t = walk(D, i, exit_rule)
        if t is None:
            continue
        out.append(t)
        free = t["x"] + 1 + cool
    return out


def per(trs):
    return {k: g.stats([t["rh"] for t in trs if t["p"] == k]) for k in KEYS}


def tv(ps):
    n = ps["train"]["n"] + ps["validate"]["n"]
    tot = ps["train"]["total"] + ps["validate"]["total"]
    return n, (tot / n if n else 0.0)


def rand_job(arg):
    tf, rows, exit_rule, seed, runs = arg
    D = load(tf)
    rng = np.random.default_rng(seed)
    n = len(D["c"])
    pools = {}
    for name in ("train", "validate", "test"):
        a, z = next((x[1], x[2]) for x in g.PERIODS if x[0] == name)
        idx = np.nonzero((D["utc"] >= a) & (D["utc"] < z))[0]
        pools[name] = idx[(idx > 400) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            tr = walk(D, int(rng.choice(pools[t["p"]])), exit_rule, t["dist_atr"])
            if tr:
                rs.append(tr["rh"])
        means.append(float(np.mean(rs)))
    return means


def p_random(tf, trs, exit_rule):
    rows = [{"p": t["p"], "dist_atr": t["dist_atr"]} for t in trs if t["p"] in ("train", "validate", "test")]
    real = float(np.mean([t["rh"] for t in trs if t["p"] in ("train", "validate", "test")]))
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(tf, rows, exit_rule, 8000 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def subset_check(D, trig, exit_rule, ctx, loc):
    """G79 method: on the unfiltered book of this trigger/exit, does the combo's context/location filter keep the better trades?"""
    base = book(D, triggers(D, trig), exit_rule)
    rows = []
    for name, f in (("bối cảnh " + ctx, lambda t: ctx_ok(D, t["i"], ctx)), ("vị trí " + loc, lambda t: loc_ok(D, t["i"], loc))):
        if (name.endswith("C0")) or (name.endswith("L0")):
            continue
        better, cells = 0, []
        for q in ("train", "validate", "test"):
            k = [t["rh"] for t in base if t["p"] == q and f(t)]
            r = [t["rh"] for t in base if t["p"] == q and not f(t)]
            mk, mr = (np.mean(k) if k else np.nan), (np.mean(r) if r else np.nan)
            better += int(bool(k) and bool(r) and mk > mr)
            cells.append(f"{q}: giữ {len(k)} / {mk:+.2f} — bỏ {len(r)} / {mr:+.2f}")
        rows.append((name, better, "; ".join(cells)))
    return rows


def main():
    L = ["# G80: Setup bán riêng trên khung nhỏ — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g80-sell-scalp.md`. XAUUSD, chỉ lệnh bán, chi phí khắt khe G68. Ô: số lệnh / R mỗi lệnh.", ""]
    grid = {}
    for tf in ("M15", "M30"):
        D = load(tf)
        sigs = {trig: triggers(D, trig) for trig in TRIG}
        for ctx, loc, trig, ex in itertools.product(CTX, LOC, TRIG, EXIT):
            sig = [i for i in sigs[trig] if ctx_ok(D, i, ctx) and loc_ok(D, i, loc)]
            grid[(tf, ctx, loc, trig, ex)] = per(book(D, sig, ex))
        sys.stdout.buffer.write(f"grid {tf}\n".encode()); sys.stdout.flush()
    L += ["## Lưới 96 bộ", "", "| Khung | Bối cảnh | Vị trí | Vào | Thoát | " + " | ".join(v.NAMES[k] for k in KEYS) + " | Train+val |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, ps in grid.items():
        n, m = tv(ps)
        L.append("| " + " | ".join(key) + " | " + " | ".join(f"{ps[k]['n']} / {ps[k]['exp']:+.3f}" if ps[k]["n"] else "—" for k in KEYS) +
                 f" | {n} / {m:+.3f} |")
    cands = [k for k, ps in grid.items() if ps["train"]["n"] and ps["validate"]["n"] and ps["train"]["exp"] > 0
             and ps["validate"]["exp"] > 0 and tv(ps)[0] >= 60]
    L += ["", f"Ứng viên (dương train và validate, ≥ 60 lệnh): {len(cands)}.", ""]
    if not cands:
        L += ["**Không bộ nào đủ điều kiện → bên bán vẫn không đạt; S07S giữ như cũ.**", ""]
    else:
        pick = max(cands, key=lambda k: tv(grid[k])[1])
        tf, ctx, loc, trig, ex = pick
        D = load(tf)
        sig = [i for i in triggers(D, trig) if ctx_ok(D, i, ctx) and loc_ok(D, i, loc)]
        trs = book(D, sig, ex)
        rm, p = p_random(tf, trs, ex)
        other = grid[("M30" if tf == "M15" else "M15", ctx, loc, trig, ex)]
        sub = subset_check(D, trig, ex, ctx, loc)
        checks = {"test > 0": grid[pick]["test"]["n"] > 0 and grid[pick]["test"]["exp"] > 0,
                  f"thắng ngẫu nhiên p < 0,05/96 (p = {p:.4f}, ngẫu nhiên TB {rm:+.3f})": p < 0.05 / N_TESTS,
                  "khung còn lại dương train và validate": other["train"]["n"] and other["validate"]["n"] and
                  other["train"]["exp"] > 0 and other["validate"]["exp"] > 0,
                  "lọc có tác dụng trên tập con (≥ 2/3 kỳ)": all(b >= 2 for _, b, _ in sub)}
        ok = all(checks.values())
        L += [f"Chọn: **{' / '.join(pick)}** — train+validate {tv(grid[pick])[0]} lệnh / {tv(grid[pick])[1]:+.3f}R.", ""]
        L += [f"- {k}: {'đạt' if x else 'KHÔNG'}" for k, x in checks.items()]
        L += [f"- tập con {n}: {cells}" for n, _, cells in sub]
        L += ["", f"**Kết luận theo luật: {'ĐẠT' if ok else 'không đạt'}.**", ""]
        # M5 check (report only)
        D5 = load("M5")
        sig5 = [i for i in triggers(D5, trig) if ctx_ok(D5, i, ctx) and loc_ok(D5, i, loc)]
        p5 = per(book(D5, sig5, ex))
        L += ["Kiểm tra M5 (từ 05/2024, chỉ báo cáo): " + ", ".join(f"{v.NAMES[k]} {p5[k]['n']} / {p5[k]['exp']:+.3f}" for k in KEYS if p5[k]["n"]), ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
