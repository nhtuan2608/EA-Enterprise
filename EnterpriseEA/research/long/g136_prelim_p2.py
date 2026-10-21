"""G136 PRELIMINARY P2 (amended 21/10/2026): S07 sells only on D1 death-cross days, on the VPS Lirunex H1 / H4 bars.

Not the plan's data source nor its M30 sell book (S07S/S07ES/S07RS/S07AS); not for decisions.
Usage: g136_prelim_p2.py <dir with h1v/ and h4v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

TFS = {"H1": (4, 2, 120), "H4": (8, 4, 240)}          # G135 H1, G81/G83 H4
SEL_END, HALF = g.ts(2024, 1, 1), g.ts(2021, 7, 1)
FWD, FWD_CLEAN = g.ts(2026, 6, 26), g.ts(2026, 10, 21)
RUNS = 200
random.seed(136)


def cell(rs):
    s = g.stats(list(rs))
    return {"n": s["n"], "exp": round(s["exp"], 3), "total": round(s["total"], 1)} if s["n"] else {"n": 0}


def run_tf(tf, comp, cool, hold, root):
    g.set_tf(tf)
    g.DATA = root / f"{tf.lower()}v"
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = comp, cool, hold
    D = g.load("XAUUSD")
    n = len(D["t"])
    day = D["t"] // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], n - 1]
    days, lc = day[ends], D["c"][ends]
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    state = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0)

    def d1(i):                                        # last CLOSED server day before bar i
        q = np.searchsorted(days, int(day[i]), side="left") - 1
        return int(state[q]) if q >= 0 else 0

    def cost(t):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        return h.harsh(t, D)

    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    rows = []
    for t in g.trades("XAUUSD", "E2X", 8.0, None, sig):
        t["rh"] = cost(t)
        t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
        t["st"] = d1(t["i"])
        rows.append(t)
    sells = [t for t in rows if t["d"] == -1]
    sel = [t for t in sells if t["utc"] < SEL_END]
    dx = [t for t in sel if t["st"] == -1]

    # random control on death-cross days 2018-2023 only: same count, direction, server hour, exit and costs
    pool = {}
    for j in range(250, n - 2):
        if int(D["utc"][j]) < SEL_END and d1(j) == -1:
            pool.setdefault(int(D["t"][j] % 86400 // 3600), []).append(j)

    def rand_mean():
        out = []
        for t in dx:
            cands = pool.get(int(D["t"][t["i"]] % 86400 // 3600)) or [j for v in pool.values() for j in v]
            for _ in range(50):
                r = g.walk(D, random.choice(cands), -1, "E2X", 8.0, None)
                if r is not None:
                    out.append(cost(r)); break
        return float(np.mean(out))

    actual = float(np.mean([t["rh"] for t in dx])) if dx else float("nan")
    p = (sum(rand_mean() >= actual for _ in range(RUNS)) + 1) / (RUNS + 1) if dx else None
    return {
        "bars": n, "first": int(D["t"][0]), "last": int(D["t"][-1]),
        "D0 bán 2018-2023": cell(t["rh"] for t in sel),
        "DX bán death 2018-2023": cell(t["rh"] for t in dx),
        "DX phí x1.5": cell(t["rh15"] for t in dx),
        "DX nửa đầu (<07/2021)": cell(t["rh"] for t in dx if t["utc"] < HALF),
        "DX nửa sau (07/2021-2023)": cell(t["rh"] for t in dx if t["utc"] >= HALF),
        "p ngẫu nhiên (ngày death)": p,
        "bán golden 2018-2026": cell(t["rh"] for t in sells if t["st"] == 1),
        "bán golden 2024-06/2026": cell(t["rh"] for t in sells if t["st"] == 1 and SEL_END <= t["utc"] < FWD),
        "forward bán death 26/06-20/10/2026 (đã xem với H1)": cell(t["rh"] for t in sells if FWD <= t["utc"] < FWD_CLEAN and t["st"] == -1),
        "forward kín từ 21/10/2026": cell(t["rh"] for t in sells if t["utc"] >= FWD_CLEAN and t["st"] == -1),
        "mua death 2018-2023 (tham khảo)": cell(t["rh"] for t in rows if t["d"] == 1 and t["st"] == -1 and t["utc"] < SEL_END),
        "mua từ 26/06/2026 (tham khảo)": cell(t["rh"] for t in rows if t["d"] == 1 and t["utc"] >= FWD),
    }


def main():
    root = Path(sys.argv[1])
    res = {tf: run_tf(tf, *cfg, root) for tf, cfg in TFS.items()}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
