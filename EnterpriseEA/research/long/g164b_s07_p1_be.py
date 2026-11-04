"""G164b: S07 + P1 (+1R step adds) with the base stop moved to break-even when the first add fills (V-P1BE), vs the S07 book (V0),
break-even at +1R alone (V-BE1), the G164 version (V-P1) and random-bar adds with break-even (V-P1BE-rand).
Plan: docs/superpowers/plans/2026-11-05-g164b-s07-p1-be.md.

Usage: g164b_s07_p1_be.py <data dir> <out dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g164_p1_bots as p  # noqa: E402

START, SPLIT, END = p.START, p.SPLIT, p.END
SEED, BOOT, ALPHA, RUNS = 1642, 2000, 0.01, 50


def sim(F, T, adds_mode, be_mode, s07_adds, rng=None, q=0.0, cost_mult=1.0, stats=None):
    """adds_mode: none | P1 | RAND ; be_mode: none | at1R | on_add. Returns (weighted R, weighted add R, n adds)."""
    o, h, l, c, sp, A, tt = F["o"], F["h"], F["l"], F["c"], F["sp"], F["atr"], F["t"]
    d, e, x, entry, dist = T["d"], T["e"], T["x"], T["entry"], T["dist"]
    cost_r = T["r"] - T["rh"]
    px = entry + d * T["r"] * dist
    slip = 0.5 * F["sp_med"] * cost_mult
    comm = p.COMM_OZ * cost_mult
    base_x, base_px = x, px
    armed_at, reached = None, False
    adds = []
    best = 0.0
    for j in range(e, x + 1):
        adv = l[j] if d == 1 else h[j]
        fav = h[j] if d == 1 else l[j]
        if be_mode != "none" and armed_at is not None and j > armed_at and d * (adv - entry) <= 0:
            base_x, base_px = j, (o[j] if d * (o[j] - entry) < 0 else entry)
            break
        if j == x:
            break
        prof = d * (fav - entry) / dist
        best = max(best, prof)
        if prof >= 1.0 and not reached:
            reached = True
            if be_mode == "at1R":
                armed_at = j
        n_before = len([a for a in adds if a is not None])
        if adds_mode == "P1":
            k = len(adds) + 1
            while k <= 3 and best >= k:
                lvl = entry + d * k * dist
                fill_ref = o[j] if d * (o[j] - lvl) > 0 else lvl
                ep = fill_ref + sp[j] + slip if d == 1 else fill_ref - slip
                lo3 = l[max(e, j - 3):j].min() if j > e else l[j]
                hi3 = h[max(e, j - 3):j].max() if j > e else h[j]
                stop = lo3 - 0.3 * A[max(j - 1, 0)] if d == 1 else hi3 + 0.3 * A[max(j - 1, 0)]
                p._try_add(adds, d, j, ep, stop, tt, s07_adds)
                k += 1
                if len(adds) < k - 1:
                    adds.append(None)
        elif adds_mode == "RAND" and reached and len([a for a in adds if a is not None]) < 3:
            if stats is not None:
                stats["elig"] += 1
            if rng.random() < q:
                ep = c[j] + sp[j] + slip if d == 1 else c[j] - slip
                stop = l[j] - 0.3 * A[j] if d == 1 else h[j] + 0.3 * A[j]
                p._try_add(adds, d, j, ep, stop, tt, s07_adds)
        if be_mode == "on_add" and armed_at is None and len([a for a in adds if a is not None]) > n_before:
            armed_at = j
    adds = [a for a in adds if a is not None]
    if stats is not None and adds_mode == "P1":
        stats["adds"] += len(adds)
    base_r = T["rh"] if (base_x == x and base_px == px) else (d * (base_px - entry) / dist - cost_r)
    add_r = 0.0
    for j0, ep, share, stop, dd in adds:
        xp, xj = base_px, base_x
        for k in range(j0 + 1, base_x + 1):
            adv = l[k] if d == 1 else h[k]
            if k == base_x:
                if d * (base_px - stop) < 0 or d * (adv - stop) <= 0:
                    xp = o[k] if d * (o[k] - stop) < 0 else stop
                break
            if d * (adv - stop) <= 0:
                xp, xj = (o[k] if d * (o[k] - stop) < 0 else stop), k
                break
        nights = max(0, int(tt[xj] // 86400 - tt[j0] // 86400))
        add_r += share * (d * (xp - ep) - (comm + slip + nights * p.SWAP_OZ * cost_mult)) / dd
    aw = T.get("al", 1.0)
    return T["w"] * base_r + aw * add_r, aw * add_r, len(adds)


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    F, trades, s07_adds = p.book_s07(root)
    extra = [(s0, s1, r, dx) for s0, s1, dx, r in s07_adds]
    rng = np.random.default_rng(SEED)

    def book(adds_mode, be_mode, **kw):
        rows, per, addr, na = [], [], 0.0, 0
        for T in trades:
            if adds_mode == "V0":
                r, ar, n_ = T["w"] * T["rh"], 0.0, 0
            else:
                r, ar, n_ = sim(F, T, adds_mode, be_mode, s07_adds, **kw)
            rows.append((T["t_in"], T["t_out"], r, T["d"]))
            per.append(r)
            addr += ar
            na += n_
        return rows + extra, np.array(per), addr, na

    def tot(rows, a=START, z=END, side=None):
        return sum(r for ti, _, r, d in rows if a <= ti < z and (side is None or d == side))

    res = {}
    v0, per0, _, _ = book("V0", "none")
    vbe, perbe, _, _ = book("none", "at1R")
    vp1, perp1, addp1, nap1 = book("P1", "none")
    st = {"elig": 0, "adds": 0}
    vpb, perpb, addpb, napb = book("P1", "on_add", stats=st)
    st_r = {"elig": 0, "adds": 0}
    book("RAND", "on_add", rng=rng, q=0.0, stats=st_r)
    q = napb / max(st_r["elig"], 1)
    rnd = [tot(book("RAND", "on_add", rng=rng, q=q)[0]) for _ in range(RUNS)]
    harsh, _, _, _ = book("P1", "on_add", cost_mult=1.5)
    check = {"V0 tổng R (G164: 316,22)": round(tot(v0), 2), "V-P1 tổng R (G164: 375,16)": round(tot(vp1), 2)}
    print("check", check, flush=True)
    P = [("05/2018–2022", START, SPLIT), ("2023–10/2026", SPLIT, END)]
    for lab, rows in (("V0", v0), ("V-BE1", vbe), ("V-P1", vp1), ("V-P1BE", vpb), ("V-P1BE chi phí × 1,5", harsh)):
        res[lab] = {pn: p.metrics(rows, a, z) for pn, a, z in P}
        res[lab]["cả kỳ"] = p.metrics(rows, START, END)
    res["V-P1"]["số lần bồi"], res["V-P1"]["R từ lệnh bồi"] = nap1, round(addp1, 2)
    res["V-P1BE"]["số lần bồi"], res["V-P1BE"]["R từ lệnh bồi"] = napb, round(addpb, 2)
    diff = {}
    for (ti, _, r1, _), (_, _, r0, _) in zip(vpb, v0):
        if START <= ti < END:
            diff[ti // (7 * 86400)] = diff.get(ti // (7 * 86400), 0.0) + r1 - r0
    W = np.array(list(diff.values()))
    bs = [W[rng.integers(0, len(W), len(W))].sum() for _ in range(BOOT)]
    ci = [round(float(np.percentile(bs, 100 * ALPHA / 2)), 2), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 2)]
    per_diff = {pn: round(tot(vpb, a, z) - tot(v0, a, z), 2) for pn, a, z in P}
    side = {s: round(tot(vpb, side=s) - tot(v0, side=s), 2) for s in (1, -1)}
    worst0, worstpb = float(per0.min()), float(perpb.min())
    crit = {"1 CI 99 % chênh > 0": ci[0] > 0,
            "2 chênh > 0 hai kỳ": all(v > 0 for v in per_diff.values()),
            "3 DD R ≤ 1,10 × V0": res["V-P1BE"]["cả kỳ"]["DD R"] <= 1.10 * res["V0"]["cả kỳ"]["DD R"],
            "4 hơn p95 bồi ngẫu nhiên (có BE)": tot(vpb) > float(np.percentile(rnd, 95)),
            "5 mua và bán ≥ 0": side[1] >= 0 and side[-1] >= 0,
            "6 chi phí × 1,5 vẫn hơn V0": tot(harsh) > tot(v0),
            "7 cụm tệ nhất không tệ hơn V0": worstpb >= worst0 - 1e-9}
    res.update({"kiểm code": check, "chênh V-P1BE − V0 theo kỳ": per_diff, "CI 99 %": ci, "chênh theo chiều (mua / bán)": [side[1], side[-1]],
                "bồi ngẫu nhiên có BE: tổng R p50 / p95": [round(float(np.percentile(rnd, 50)), 2), round(float(np.percentile(rnd, 95)), 2)],
                "tỷ lệ bồi ngẫu nhiên": round(q, 4), "cụm tệ nhất (R có trọng số): V0 / V-P1BE": [round(worst0, 3), round(worstpb, 3)],
                "chênh V-BE1 − V0": round(tot(vbe) - tot(v0), 2), "chênh V-P1 − V0": round(tot(vp1) - tot(v0), 2),
                "tiêu chí": crit, "đạt": all(crit.values())})
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    for lab in ("V0", "V-BE1", "V-P1", "V-P1BE"):
        print(lab, res[lab]["cả kỳ"], "| chọn", res[lab]["05/2018–2022"]["tổng R"], "| kiểm", res[lab]["2023–10/2026"]["tổng R"], flush=True)
    print("diff", per_diff, "CI", ci, "| rand", res["bồi ngẫu nhiên có BE: tổng R p50 / p95"], "| sides", side, "| worst", res["cụm tệ nhất (R có trọng số): V0 / V-P1BE"],
          "| harsh", round(tot(harsh), 2), "\n crit", crit, "\n done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
