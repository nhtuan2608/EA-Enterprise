"""G164c: W1 (previous-week breakout, D1-aligned) with the stop moved to break-even at +X R, on XAU (seen in G164, alpha 0.01) and as a
transfer test on BTCUSD / EURUSD (ETH, SP500, NAS100 report only). Plan: docs/superpowers/plans/2026-11-05-g164c-w1-be.md.

Usage: g164c_w1_be.py <data dir> <out dir>
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
SEED, BOOT = 1643, 2000
WEEK = 7 * 86400


def book_w1(root, sym):
    import g147_risk_map as rm
    import g148_layered_risk_map as lm
    import g149_repeating as rp
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load(sym))
    cx = rp.Ctx(D, lm.bar_context(D), lm.daily_context(D))
    reg = p.regime_bars(D)
    rows = [t for t in rp.w1(cx, 0) if t and int(reg[t["e"]]) * t["d"] == 1]
    F = p.frame_of(D, D["comm"])
    return F, [dict(d=t["d"], e=t["e"], x=t["x"], entry=t["entry"], dist=t["risk"], r=t["r"], rh=t["rh"], w=1.0,
                    t_in=int(D["t"][t["e"]]), t_out=int(D["t"][t["x"]])) for t in rows]


def sim_be(F, T, level, slip_mult=1.0):
    """R of one W1 trade with break-even armed once price reaches +level R (None = book)."""
    if level is None:
        return T["rh"]
    o, h, l = F["o"], F["h"], F["l"]
    d, e, x, entry, dist = T["d"], T["e"], T["x"], T["entry"], T["dist"]
    cost_r = T["r"] - T["rh"]
    armed = None
    for j in range(e, x + 1):
        adv = l[j] if d == 1 else h[j]
        if armed is not None and j > armed and d * (adv - entry) <= 0:
            px = o[j] if d * (o[j] - entry) < 0 else entry
            extra = 0.5 * F["sp_med"] * slip_mult / dist                      # extra slippage on the break-even exit
            return d * (px - entry) / dist - cost_r - extra
        if j == x:
            break
        fav = h[j] if d == 1 else l[j]
        if armed is None and d * (fav - entry) / dist >= level:
            armed = j
    return T["rh"]


def ci_diff(trades, r1, r0, rng, alpha):
    diff = {}
    for T, a, b in zip(trades, r1, r0):
        diff[T["t_in"] // WEEK] = diff.get(T["t_in"] // WEEK, 0.0) + a - b
    W = np.array(list(diff.values()))
    if len(W) < 5:
        return None
    bs = [W[rng.integers(0, len(W), len(W))].sum() for _ in range(BOOT)]
    return [round(float(np.percentile(bs, 100 * alpha / 2)), 2), round(float(np.percentile(bs, 100 * (1 - alpha / 2))), 2)]


def summary(trades, rs, a=None, z=None):
    rows = [(T["t_in"], T["t_out"], r, T["d"]) for T, r in zip(trades, rs)]
    a = a if a is not None else min(T["t_in"] for T in trades)
    z = z if z is not None else max(T["t_in"] for T in trades) + 1
    return p.metrics(rows, a, z)


def main():
    root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    res = {}
    # ---- XAU (main test)
    F, tr = book_w1(root, "XAUUSD")
    tr = [T for T in tr if START <= T["t_in"] < END]
    r0 = np.array([sim_be(F, T, None) for T in tr])
    r1 = np.array([sim_be(F, T, 1.0) for T in tr])
    r075 = np.array([sim_be(F, T, 0.75) for T in tr])
    r15 = np.array([sim_be(F, T, 1.5) for T in tr])
    r1h = np.array([sim_be(F, T, 1.0, slip_mult=2.0) for T in tr])
    sel = np.array([T["t_in"] < SPLIT for T in tr])
    side = np.array([T["d"] for T in tr])
    x = {"kiểm code: V0 tổng R (G164: 36,93)": round(float(r0.sum()), 2), "V-BE1 tổng R (G164 không trượt thêm: 47,35)": round(float(r1.sum()), 2)}
    res["XAUUSD"] = {"số lệnh": len(tr), "V0": summary(tr, r0, START, END), "V-BE1": summary(tr, r1, START, END),
                     "V-BE0,75": summary(tr, r075, START, END), "V-BE1,5": summary(tr, r15, START, END),
                     "chênh V-BE1 − V0: kỳ chọn / kỳ kiểm": [round(float((r1 - r0)[sel].sum()), 2), round(float((r1 - r0)[~sel].sum()), 2)],
                     "chênh mua / bán": [round(float((r1 - r0)[side == 1].sum()), 2), round(float((r1 - r0)[side == -1].sum()), 2)],
                     "CI 99 %": ci_diff(tr, r1, r0, rng, 0.01), "chênh láng giềng 0,75 / 1,5": [round(float((r075 - r0).sum()), 2), round(float((r15 - r0).sum()), 2)],
                     "chênh khi trượt giá BE × 2": round(float((r1h - r0).sum()), 2), "kiểm code": x}
    xa = res["XAUUSD"]
    print("XAU", x, "| V0", xa["V0"], "| BE1", xa["V-BE1"], "| per", xa["chênh V-BE1 − V0: kỳ chọn / kỳ kiểm"], "| sides", xa["chênh mua / bán"],
          "| CI", xa["CI 99 %"], "| nb", xa["chênh láng giềng 0,75 / 1,5"], "| harsh", xa["chênh khi trượt giá BE × 2"], flush=True)
    # ---- transfer
    for sym in ("BTCUSD", "EURUSD", "ETHUSD", "SP500", "NAS100"):
        try:
            Fs, ts = book_w1(root, sym)
        except Exception as ex:                                              # noqa: BLE001
            res[sym] = {"lỗi": str(ex)}
            print(sym, "error", ex, flush=True)
            continue
        if not ts:
            res[sym] = {"số lệnh": 0}
            continue
        a0 = np.array([sim_be(Fs, T, None) for T in ts])
        a1 = np.array([sim_be(Fs, T, 1.0) for T in ts])
        res[sym] = {"số lệnh": len(ts), "từ": str(np.datetime64(min(T["t_in"] for T in ts), "s")), "V0": summary(ts, a0), "V-BE1": summary(ts, a1),
                    "chênh": round(float((a1 - a0).sum()), 2), "CI 95 %": ci_diff(ts, a1, a0, rng, 0.05),
                    "chênh mua / bán": [round(float((a1 - a0)[np.array([T["d"] == 1 for T in ts])].sum()), 2),
                                        round(float((a1 - a0)[np.array([T["d"] == -1 for T in ts])].sum()), 2)]}
        print(sym, res[sym]["số lệnh"], "| V0 R", res[sym]["V0"]["tổng R"], "DD", res[sym]["V0"].get("DD R"), "| BE1 R", res[sym]["V-BE1"]["tổng R"],
              "DD", res[sym]["V-BE1"].get("DD R"), "| chênh", res[sym]["chênh"], res[sym]["CI 95 %"], res[sym]["chênh mua / bán"], flush=True)
    crit = {"1 CI 99 % > 0 (XAU)": xa["CI 99 %"] is not None and xa["CI 99 %"][0] > 0,
            "2 chênh > 0 hai kỳ (XAU)": all(v > 0 for v in xa["chênh V-BE1 − V0: kỳ chọn / kỳ kiểm"]),
            "3 mua và bán ≥ 0 (XAU)": all(v >= 0 for v in xa["chênh mua / bán"]),
            "4 DD không tăng (XAU)": xa["V-BE1"]["DD R"] <= xa["V0"]["DD R"],
            "5 láng giềng 0,75 / 1,5 > 0": all(v > 0 for v in xa["chênh láng giềng 0,75 / 1,5"]),
            "6 chuyển giao BTC và EUR > 0": all(res.get(s, {}).get("chênh", -1) > 0 for s in ("BTCUSD", "EURUSD")),
            "7 trượt giá BE × 2 vẫn > 0": xa["chênh khi trượt giá BE × 2"] > 0}
    res["tiêu chí"], res["đạt"] = crit, all(crit.values())
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("crit", crit, "| done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
