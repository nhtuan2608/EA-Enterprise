"""G163b: P2 in-profit confirmed pullback adds on the S07 book - replacing (B-P2) or on top of (B-P2+) the S07 ADD legs, vs random-bar
adds. Plan: docs/superpowers/plans/2026-11-04-g163-loose-zone-pyramid.md (branch b).

Usage: g163b_s07_pyramid.py <data dir> <out dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g136_p1p4 as p4  # noqa: E402
import g162b_s07_scale_in as sb  # noqa: E402

START, SPLIT, END = sb.START, sb.SPLIT, sb.END
SEED, BOOT, WEEK, ALPHA = 163, 2000, 7 * 86400, 0.05 / 2


def swings(h, l):
    n = len(h)
    lo, hi = np.full(n, np.nan), np.full(n, np.nan)
    cl = ch = np.nan
    for i in range(n):
        j = i - 5
        if j >= 5:
            if l[j] == l[j - 5:j + 6].min():
                cl = l[j]
            if h[j] == h[j - 5:j + 6].max():
                ch = h[j]
        lo[i], hi[i] = cl, ch
    return lo, hi


def p2_adds(L, M, add_legs, plus, rng=None, q=0.0, stats=None):
    """R (in units of the base 1R, before the alignment weight) of P2 adds on one S07 base leg."""
    t, o, h, l, c, sp, A, e21 = M["t"], M["o"], M["h"], M["l"], M["c"], M["sp"], M["atr"], M["e21"]
    d, e, dist = L["d"], L["entry"], L["dist"]
    exit_px = e + d * (L["r"] * dist + L["comm"])
    slip = 0.5 * M["sp_med"]
    cost = L["comm"] + 2 * slip
    a = int(np.searchsorted(t, L["srv_in"], side="right"))
    z = int(np.searchsorted(t, L["srv_out"], side="right")) - 1
    best, adds, total = 0.0, [], 0.0
    for j in range(a, z):
        fav = h[j] if d == 1 else l[j]
        best = max(best, d * (fav - e) / dist)
        if best < 1.0 or len(adds) >= 3:
            continue
        if stats is not None:
            stats["elig"] += 1
        if q > 0:
            do = rng.random() < q
        else:
            rg = h[j] - l[j]
            wick = (min(o[j], c[j]) - l[j]) if d == 1 else (h[j] - max(o[j], c[j]))
            if not (rg > 0 and wick >= 0.5 * rg and d * (c[j] - o[j]) > 0):
                continue
            ext = l[j] if d == 1 else h[j]
            lv = [e21[j], M["pdl"][j] if d == 1 else M["pdh"][j]]
            sw = M["swh"][j] if d == 1 else M["swl"][j]
            if np.isfinite(sw) and d * (c[j] - sw) > 0:
                lv.append(sw)
            do = any(np.isfinite(v) and d * (ext - v) <= 0 < d * (c[j] - v) for v in lv)
        if not do:
            continue
        ep = c[j] + sp[j] + slip if d == 1 else c[j] - slip
        stop = l[j] - 0.3 * A[j] if d == 1 else h[j] + 0.3 * A[j]
        dd = d * (ep - stop)
        if dd <= 0:
            continue
        used = sum(x[2] for x in adds)
        if plus:
            used += sum(0.67 for s0, s1, dx in add_legs if dx == d and s0 <= t[j] < s1)
        share = min(1.0, 1.0 - used)
        if share < 0.05:
            continue
        adds.append((j, ep, share, stop, dd))
        if stats is not None:
            stats["adds"] += 1
    for j, ep, share, stop, dd in adds:
        xp = exit_px
        for k in range(j + 1, z + 1):
            adv = l[k] if d == 1 else h[k]
            if k == z:
                if d * (exit_px - stop) < 0:
                    xp = stop
                break
            if d * (adv - stop) <= 0:
                xp = o[k] if d * (o[k] - stop) < 0 else stop
                break
        total += share * (d * (xp - ep) - cost) / dd
    return total, len(adds)


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    legs = [x for x in sb.book() if START <= x["srv_in"] < END]
    d1 = p4.d1_from("M30")
    for x in legs:
        x["al"] = 1.0 if d1(x["srv_in"]) == x["d"] else 0.5
        x["wt"] = x["w"] * x["al"]
    g.set_tf("M30")
    g.DATA = root / "m30v"
    M = g.load("XAUUSD")
    M["e21"] = g.ema(M["c"], 21)
    M["swl"], M["swh"] = swings(M["h"], M["l"])
    day = M["t"] // 86400
    starts = np.r_[0, np.nonzero(np.diff(day))[0] + 1]
    ends = np.r_[starts[1:], len(day)]
    dl = np.array([M["l"][a:z].min() for a, z in zip(starts, ends)])
    dh = np.array([M["h"][a:z].max() for a, z in zip(starts, ends)])
    pos = np.searchsorted(starts, np.arange(len(day)), side="right") - 2
    M["pdl"] = np.where(pos >= 0, dl[np.maximum(pos, 0)], np.nan)
    M["pdh"] = np.where(pos >= 0, dh[np.maximum(pos, 0)], np.nan)
    bases = [x for x in legs if x["base"]]
    s07_adds = [x for x in legs if not x["base"]]
    add_spans = [(x["srv_in"], x["srv_out"], x["d"]) for x in s07_adds]

    def book_rows(variant, rng=None, q=0.0, stats=None):
        rows, per = [], []
        for x in bases:
            r = x["wt"] * x["rh"]
            if variant != "B0":
                ar, _ = p2_adds(x, M, add_spans, variant == "B-P2+", rng=rng, q=q, stats=stats)
                r += x["al"] * ar
            per.append(r)
            rows.append((x["srv_out"], r, x["srv_in"], x["d"]))
        if variant in ("B0", "B-P2+"):
            rows += [(x["srv_out"], x["wt"] * x["rh"], x["srv_in"], x["d"]) for x in s07_adds]
        return rows, np.array(per)

    def met(rows, a, z):
        return sb.metrics([(so, r) for so, r, si, d in rows if a <= si < z])

    res = {}
    rows0, per0 = book_rows("B0")
    res["B0"] = {"kỳ chọn": met(rows0, START, SPLIT), "kỳ kiểm": met(rows0, SPLIT, END), "cả kỳ": met(rows0, START, END)}
    print("B0", res["B0"], flush=True)
    rng = np.random.default_rng(SEED)
    wk = np.array([x["srv_in"] // WEEK for x in bases])
    uw = np.unique(wk)
    for v in ("B-P2", "B-P2+"):
        st = {"elig": 0, "adds": 0}
        rows, per = book_rows(v, stats=st)
        # weekly difference vs B0 including the removed / kept S07 ADD legs
        tot_w = {}
        for so, r, si, d in rows:
            tot_w[si // WEEK] = tot_w.get(si // WEEK, 0.0) + r
        for so, r, si, d in rows0:
            tot_w[si // WEEK] = tot_w.get(si // WEEK, 0.0) - r
        W = np.array(list(tot_w.values()))
        bs = [W[rng.integers(0, len(W), len(W))].sum() for _ in range(BOOT)]
        ci = [round(float(np.percentile(bs, 100 * ALPHA / 2)), 2), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 2)]
        sel, kk, full = met(rows, START, SPLIT), met(rows, SPLIT, END), met(rows, START, END)
        q = st["adds"] / max(st["elig"], 1)
        rnd = []
        for _ in range(50):
            rr, _p = book_rows(v, rng=rng, q=q)
            rnd.append(met(rr, START, END)["tổng R"])
        side = {}
        for s in (1, -1):
            side[s] = round(sum(r for so, r, si, d in rows if d == s) - sum(r for so, r, si, d in rows0 if d == s), 2)
        crit = {"1 CI chênh > 0": ci[0] > 0,
                "2 hơn B0 cả hai kỳ": sel["tổng R"] > res["B0"]["kỳ chọn"]["tổng R"] and kk["tổng R"] > res["B0"]["kỳ kiểm"]["tổng R"],
                "3 DD R không tệ hơn 10 %": full["DD R"] <= 1.10 * res["B0"]["cả kỳ"]["DD R"],
                "4 hơn p95 bồi ngẫu nhiên": full["tổng R"] > float(np.percentile(rnd, 95)),
                "5 mua và bán ≥ 0": side[1] >= 0 and side[-1] >= 0}
        res[v] = {"kỳ chọn": sel, "kỳ kiểm": kk, "cả kỳ": full, "chênh tổng R so với B0": round(full["tổng R"] - res["B0"]["cả kỳ"]["tổng R"], 2),
                  f"CI {1 - ALPHA:.1%}": ci, "số lần bồi P2": st["adds"], "bồi ngẫu nhiên tổng R p50 / p95": [float(np.percentile(rnd, 50)),
                                                                                                             float(np.percentile(rnd, 95))],
                  "chênh theo chiều (mua / bán)": [side[1], side[-1]], "tiêu chí": crit, "đạt": all(crit.values())}
        print(v, "| chênh", res[v]["chênh tổng R so với B0"], ci, "| bồi", st["adds"], "| chọn", sel, "| kiểm", kk, "| rand", res[v]["bồi ngẫu nhiên tổng R p50 / p95"],
              "| chiều", side, "| ĐẠT" if res[v]["đạt"] else "", flush=True)
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
