"""G164: the +1R step pyramid module (P1) on the running bots - XRT (D1), SQZ and W1 (M30, D1-aligned), and on top of the S07 ADD legs.
Variants: V0 as the book, V-BE (stop to break-even at +1R), V-P1 (V-BE + adds at +1/+2/+3R), V-P1-rand (adds on random in-profit bars).
Plan: docs/superpowers/plans/2026-11-04-g164-p1-on-bots.md.

Usage: g164_p1_bots.py <data dir> <out dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402

START, SPLIT, END = g.ts(2018, 5, 1), g.ts(2023, 1, 1), g.ts(2026, 11, 1)
X0 = g.ts(2010, 1, 1)
SEED, BOOT, ALPHA, RUNS = 164, 2000, 0.05 / 4, 50
COMM_OZ, SWAP_OZ = 0.06, 0.30

_orig_run_trade = gp.run_trade


def _run_trade(D, e, d, entry, sl, tp, hold, zexit=None):
    t = _orig_run_trade(D, e, d, entry, sl, tp, hold, zexit)
    if t:
        t["entry"], t["sl"] = float(entry), float(sl)
    return t


gp.run_trade = _run_trade


# ---------------------------------------------------------------------------------------------------- books
def frame_of(D, comm):
    return {"t": D["t"], "o": D["o"], "h": D["h"], "l": D["l"], "c": D["c"], "sp": D["sp"], "atr": D["atr"],
            "sp_med": float(np.median(D["sp"])), "comm": comm}


def regime_bars(D):
    import g153_regime_gated as gr
    return gr.regime(D)


def book_sqz(root):
    import g139_hybrid as hy
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = hy.prepare(g.load("XAUUSD"))
    reg = regime_bars(D)
    rows = [t for t in hy.csq(D) if t and int(reg[t["e"]]) * t["d"] == 1]
    F = frame_of(D, D["comm"])
    return F, [dict(d=t["d"], e=t["e"], x=t["x"], entry=t["entry"], dist=t["risk"], r=t["r"], rh=t["rh"], w=1.0,
                    t_in=int(D["t"][t["e"]]), t_out=int(D["t"][t["x"]])) for t in rows]


def book_w1(root):
    import g147_risk_map as rm
    import g148_layered_risk_map as lm
    import g149_repeating as rp
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    cx = rp.Ctx(D, lm.bar_context(D), lm.daily_context(D))
    reg = regime_bars(D)
    rows = [t for t in rp.w1(cx, 0) if t and int(reg[t["e"]]) * t["d"] == 1]
    F = frame_of(D, D["comm"])
    return F, [dict(d=t["d"], e=t["e"], x=t["x"], entry=t["entry"], dist=t["risk"], r=t["r"], rh=t["rh"], w=1.0,
                    t_in=int(D["t"][t["e"]]), t_out=int(D["t"][t["x"]])) for t in rows]


def book_xrt(root):
    import g96_regime as g96
    import g107_portfolio as pf
    g96.HERE = root.parent
    d = g96.load_d1()
    t = np.array([x.value // 10 ** 9 for x in d["day"]], dtype=np.int64)
    F = {"t": t, "o": d["open"].to_numpy(), "h": d["high"].to_numpy(), "l": d["low"].to_numpy(), "c": d["close"].to_numpy(),
         "sp": d["spread"].to_numpy(), "atr": d["atr"].to_numpy(), "sp_med": float(d["spread"].median()), "comm": 0.0}
    pf.load_d1 = g96.load_d1
    legs = pf.xrt_legs()
    pos = {int(v): k for k, v in enumerate(t)}
    out = []
    for L in legs:
        e = pos[int(L["t_in"].value // 10 ** 9)]
        x = pos[int(L["t_out"].value // 10 ** 9)]
        # book R already nets the 0.30 spread; treat it as the cost so that V0 reproduces r exactly
        out.append(dict(d=1, e=e, x=x, entry=float(L["entry"]), dist=float(L["risk"]), r=float(L["r"]) + 0.30 / float(L["risk"]),
                        rh=float(L["r"]), w=1.0, t_in=int(t[e]), t_out=int(t[x]), cost_fixed=0.30))
    return F, out


def book_s07(root):
    import g136_p1p4 as p4
    import g162b_s07_scale_in as sb
    legs = [x for x in sb.book() if START <= x["srv_in"] < END]
    d1 = p4.d1_from("M30")
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = g.load("XAUUSD")
    F = frame_of(D, None)
    tt = D["t"]
    out, adds = [], []
    for x in legs:
        al = 1.0 if d1(x["srv_in"]) == x["d"] else 0.5
        if not x["base"]:
            adds.append((x["srv_in"], x["srv_out"], x["d"], x["w"] * al * x["rh"]))
            continue
        e = int(np.searchsorted(tt, x["srv_in"], side="left"))
        xx = int(np.searchsorted(tt, x["srv_out"], side="right")) - 1
        out.append(dict(d=x["d"], e=e, x=xx, entry=x["entry"], dist=x["dist"], r=x["r"] + x["comm"] / x["dist"], rh=x["rh"],
                        w=x["w"] * al, al=al, comm=x["comm"], t_in=x["srv_in"], t_out=x["srv_out"]))
    return F, out, adds


# ---------------------------------------------------------------------------------------------------- engine
def simulate(F, T, mode, rng=None, q=0.0, cost_mult=1.0, s07_adds=None, stats=None, be=True):
    """Weighted R of one trade. T['r'] is the gross R (exit - entry) / dist; T['rh'] the book's net R."""
    o, h, l, c, sp, A, tt = F["o"], F["h"], F["l"], F["c"], F["sp"], F["atr"], F["t"]
    d, e, x, entry, dist = T["d"], T["e"], T["x"], T["entry"], T["dist"]
    cost_r = T["r"] - T["rh"]                                   # book costs in R (kept for the base leg)
    px = entry + d * T["r"] * dist                               # book exit price
    if mode == "V0":
        return T["w"] * T["rh"], 0.0, 0
    slip = 0.5 * F["sp_med"] * cost_mult
    comm = (F["comm"] if F["comm"] else COMM_OZ) * cost_mult
    daily = (tt[1] - tt[0]) >= 86400 if len(tt) > 1 else False
    base_x, base_px = x, px
    armed_at = None
    adds = []
    best = 0.0
    for j in range(e, x + 1):
        adv = l[j] if d == 1 else h[j]
        fav = h[j] if d == 1 else l[j]
        if be and armed_at is not None and j > armed_at and d * (adv - entry) <= 0:
            base_x, base_px = j, (o[j] if d * (o[j] - entry) < 0 else entry)
            break
        if j == x:
            break
        prof = d * (fav - entry) / dist
        if prof >= 1.0 and armed_at is None:
            armed_at = j
        best = max(best, prof)
        if mode == "P1":
            k = len(adds) + 1
            while k <= 3 and best >= k:
                lvl = entry + d * k * dist
                fill_ref = o[j] if d * (o[j] - lvl) > 0 else lvl
                ep = fill_ref + sp[j] + slip if d == 1 else fill_ref - slip
                lo3 = l[max(e, j - 3):j].min() if j > e else l[j]
                hi3 = h[max(e, j - 3):j].max() if j > e else h[j]
                stop = lo3 - 0.3 * A[max(j - 1, 0)] if d == 1 else hi3 + 0.3 * A[max(j - 1, 0)]
                _try_add(adds, d, j, ep, stop, tt, s07_adds)
                k += 1
                if len(adds) < k - 1:
                    adds.append(None)                            # level used even when skipped
        elif mode == "RAND" and armed_at is not None and j > armed_at:
            if len([a for a in adds if a is not None]) < 3:
                if stats is not None:
                    stats["elig"] += 1
                if rng.random() < q:
                    ep = c[j] + sp[j] + slip if d == 1 else c[j] - slip
                    stop = l[j] - 0.3 * A[j] if d == 1 else h[j] + 0.3 * A[j]
                    _try_add(adds, d, j, ep, stop, tt, s07_adds)
    adds = [a for a in adds if a is not None]
    if stats is not None and mode == "P1":
        stats["adds"] += len(adds)
    base_r = T["rh"] if base_x == x and base_px == px else (d * (base_px - entry) / dist - cost_r)
    if not be:
        base_r = T["rh"]
    add_r = 0.0
    for j0, ep, share, stop, dd in adds:
        xp, xj = base_px, base_x
        for k in range(j0 + 1, base_x + 1):
            adv = l[k] if d == 1 else h[k]
            if k == base_x:
                if d * (base_px - stop) < 0 or d * (adv - stop) <= 0:     # pessimistic: a touch in the exit bar stops the add
                    xp = o[k] if d * (o[k] - stop) < 0 else stop
                break
            if d * (adv - stop) <= 0:
                xp, xj = (o[k] if d * (o[k] - stop) < 0 else stop), k
                break
        nights = max(0, int((tt[xj] - tt[j0]) // 86400)) if daily else max(0, int(tt[xj] // 86400 - tt[j0] // 86400))
        cost = comm + slip + nights * SWAP_OZ * cost_mult + T.get("cost_fixed", 0.0) * 0
        add_r += share * (d * (xp - ep) - cost) / dd
    wt = T["w"]
    add_w = T.get("al", 1.0)
    return wt * base_r + add_w * add_r, add_w * add_r, len(adds)


def _try_add(adds, d, j, ep, stop, tt, s07_adds):
    dd = d * (ep - stop)
    if dd <= 0:
        return
    used = sum(a[2] for a in adds if a is not None)
    if s07_adds is not None:
        used += sum(0.67 for s0, s1, dx, _ in s07_adds if dx == d and s0 <= tt[j] < s1)
    share = min(1.0, 1.0 - used)
    if share < 0.05:
        return
    adds.append((j, ep, share, stop, dd))


# ---------------------------------------------------------------------------------------------------- stats
def metrics(rows, a, z):
    x = sorted((to, r) for ti, to, r, d in rows if a <= ti < z)
    if not x:
        return {"n": 0, "tổng R": 0.0}
    r = np.array([v for _, v in x])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    return {"n": len(r), "tổng R": round(float(r.sum()), 2), "R TB": round(float(r.mean()), 3), "PF": round(float(pos / neg), 2) if neg > 0 else None,
            "DD R": round(dd, 2), "MAR": round(float(r.sum()) / dd, 2) if dd > 0 else None}


def evaluate(name, F, trades, periods, block, rng, s07_adds=None):
    extra = [(s0, s1, r, dx) for s0, s1, dx, r in s07_adds] if s07_adds else []
    be = s07_adds is None

    def book(mode, **kw):
        rows, addr, n_add = [], 0.0, 0
        st = kw.pop("stats", None)
        for T in trades:
            r, ar, na = simulate(F, T, mode, stats=st, s07_adds=s07_adds, be=be and mode != "V0", **kw)
            rows.append((T["t_in"], T["t_out"], r, T["d"]))
            addr += ar
            n_add += na
        return rows + extra, addr, n_add

    out = {}
    v0, _, _ = book("V0")
    st = {"elig": 0, "adds": 0}
    vbe, _, _ = book("BE") if be else (None, 0, 0)
    vp1, add_r, n_add = book("P1", stats=st)
    st_r = {"elig": 0, "adds": 0}
    book("RAND", rng=rng, q=0.0, stats=st_r)
    q = n_add / max(st_r["elig"], 1)
    rnd = [sum(r for _, _, r, _ in book("RAND", rng=rng, q=q)[0]) for _ in range(RUNS)]
    harsh, _, _ = book("P1", cost_mult=1.5)
    allp = (periods[0][1], periods[-1][2])
    for lab, rows in (("V0", v0), ("V-BE", vbe), ("V-P1", vp1), ("V-P1 chi phí × 1,5", harsh)):
        if rows is None:
            continue
        out[lab] = {pn: metrics(rows, a, z) for pn, a, z in periods}
        out[lab]["cả kỳ"] = metrics(rows, *allp)
    out["V-P1"]["R từ lệnh bồi"] = round(add_r, 2)
    out["V-P1"]["số lần bồi"] = n_add
    # paired difference V-P1 - V0 by block
    diff = {}
    for (ti, _, r1, _), (_, _, r0, _) in zip(vp1, v0):
        if allp[0] <= ti < allp[1]:
            diff[ti // block] = diff.get(ti // block, 0.0) + r1 - r0
    W = np.array(list(diff.values()))
    bs = [W[rng.integers(0, len(W), len(W))].sum() for _ in range(BOOT)]
    ci = [round(float(np.percentile(bs, 100 * ALPHA / 2)), 2), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 2)]
    tot = lambda rows: sum(r for ti, _, r, _ in rows if allp[0] <= ti < allp[1])  # noqa: E731
    per_diff = {pn: round(metrics(vp1, a, z)["tổng R"] - metrics(v0, a, z)["tổng R"], 2) for pn, a, z in periods}
    side = {s: round(sum(r for ti, _, r, d in vp1 if d == s and allp[0] <= ti < allp[1]) -
                     sum(r for ti, _, r, d in v0 if d == s and allp[0] <= ti < allp[1]), 2) for s in (1, -1)}
    has_sell = any(T["d"] == -1 for T in trades)
    crit = {"1 CI chênh > 0": ci[0] > 0,
            "2 chênh > 0 mọi kỳ": all(v > 0 for v in per_diff.values()),
            "3 DD R không tệ hơn 10 %": out["V-P1"]["cả kỳ"]["DD R"] <= 1.10 * out["V0"]["cả kỳ"]["DD R"],
            "4 hơn p95 bồi ngẫu nhiên": tot(vp1) > float(np.percentile(rnd, 95)),
            "5 mua và bán ≥ 0": side[1] >= 0 and (side[-1] >= 0 or not has_sell),
            "6 chi phí × 1,5 vẫn hơn V0": tot(harsh) > tot(v0)}
    out.update({"chênh V-P1 − V0 theo kỳ": per_diff, f"CI {1 - ALPHA:.2%}": ci, "chênh theo chiều (mua / bán)": [side[1], side[-1]],
                "bồi ngẫu nhiên tổng R p50 / p95": [round(float(np.percentile(rnd, 50)), 2), round(float(np.percentile(rnd, 95)), 2)],
                "tỷ lệ bồi ngẫu nhiên": round(q, 4), "tiêu chí": crit, "đạt": all(crit.values())})
    if vbe is not None:
        out["chênh V-BE − V0 cả kỳ"] = round(tot(vbe) - tot(v0), 2)
    print(name, "| V0", out["V0"]["cả kỳ"], "| BE", out.get("V-BE", {}).get("cả kỳ"), "| P1", out["V-P1"]["cả kỳ"], "bồi", n_add, round(add_r, 1),
          "| theo kỳ", per_diff, "| CI", ci, "| rand", out["bồi ngẫu nhiên tổng R p50 / p95"], "| chiều", side, "|", crit, flush=True)
    return out


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    res = {}
    P_m30 = [("05/2018–2022", START, SPLIT), ("2023–10/2026", SPLIT, END)]
    P_d1 = [("2010–2017", X0, g.ts(2018, 1, 1)), ("2018–2022", g.ts(2018, 1, 1), SPLIT), ("2023–10/2026", SPLIT, END)]
    checks = {}
    for name, builder, periods, block in (("XRT", book_xrt, P_d1, 30 * 86400), ("SQZ", book_sqz, P_m30, 7 * 86400),
                                          ("W1", book_w1, P_m30, 7 * 86400)):
        F, trades = builder(root)
        trades = [T for T in trades if periods[0][1] <= T["t_in"] < periods[-1][2]]
        checks[name] = max(abs(simulate(F, T, "V0")[0] - T["rh"]) for T in trades)
        res[name] = evaluate(name, F, trades, periods, block, rng)
        res[name]["số lệnh"] = len(trades)
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    F, trades, s07_adds = book_s07(root)
    res["S07 + P1"] = evaluate("S07+P1", F, trades, P_m30, 7 * 86400, rng, s07_adds=s07_adds)
    res["S07 + P1"]["số lệnh gốc"] = len(trades)
    res["kiểm code: max |V0 − R sổ|"] = {k: round(v, 9) for k, v in checks.items()}
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("checks", res["kiểm code: max |V0 − R sổ|"], "done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
