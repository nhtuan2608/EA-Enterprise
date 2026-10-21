"""G136 PRELIMINARY: the H1 parts of P1 and P4 on the VPS Lirunex XAUUSD.r H1 bars (not the plan's data source).

Usage: g136_prelim_h1.py <dir holding XAUUSD.csv (time,open,high,low,close,tickvol,spread)> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

PER = [("sớm", g.ts(2018, 1, 1), g.ts(2021, 7, 1)), ("train", g.ts(2021, 7, 1), g.ts(2024, 1, 1)),
       ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)), ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1)),
       ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
DECIDE = ("train", "validate", "test")
RUNS, PERMS = 200, 2000
random.seed(136)
np.random.seed(136)


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def stats(rs):
    s = g.stats(list(rs))
    return s


def cell(rs):
    s = stats(rs)
    return f"{s['n']} / {s['exp']:+.3f} / {s['total']:+.1f}" if s["n"] else "—"


def main():
    g.set_tf("H1")
    g.DATA = Path(sys.argv[1])
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = 4, 2, 120          # G135 H1
    D = g.load("XAUUSD")
    n = len(D["t"])
    # D1 SMA50 / SMA200 state of the last CLOSED server day (as G135 d1_state on M30)
    day = D["t"] // 86400
    days, last_close = [], []
    for k in range(n):
        if k + 1 == n or day[k + 1] != day[k]:
            days.append(int(day[k])); last_close.append(float(D["c"][k]))
    days = np.array(days); lc = np.array(last_close)
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    state = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0)

    def d1(i):
        q = np.searchsorted(days, int(day[i]), side="left") - 1
        return int(state[q]) if q >= 0 else 0

    def finish(t):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        t["rh"] = h.harsh(t, D)
        t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
        t["p"] = period(t["utc"])
        t["wave"] = d1(t["i"]) * t["d"]
        return t

    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    base = [finish(t) for t in g.trades("XAUUSD", "E2X", 8.0, None, sig)]
    base = [t for t in base if t["p"]]

    # random control: same count, direction, server hour and period, same exit and costs
    by_hour = {}
    for j in range(250, n - 2):
        p = period(int(D["utc"][j]))
        if p:
            by_hour.setdefault((p, int(D["t"][j] % 86400 // 3600)), []).append(j)

    def random_mean(rows):
        out = []
        for t in rows:
            pool = by_hour.get((t["p"], int(D["t"][t["i"]] % 86400 // 3600)), [])
            for _ in range(50):
                j = random.choice(pool)
                r = g.walk(D, j, t["d"], "E2X", 8.0, None)
                if r is not None:
                    r["srv_in"], r["srv_out"] = int(D["t"][r["e0"]]), int(D["t"][r["x"]])
                    out.append(h.harsh(r, D))
                    break
        return float(np.mean(out)) if out else 0.0

    def p_random(rows):
        if not rows:
            return float("nan")
        actual = float(np.mean([t["rh"] for t in rows]))
        hits = sum(random_mean(rows) >= actual for _ in range(RUNS))
        return (hits + 1) / (RUNS + 1)

    def sim(rows, risk):
        rows = sorted(rows, key=lambda t: t["utc"])
        eq = peak = 1.0; dd = 0.0
        for t in rows:
            eq *= 1 + risk * t["rh"]; peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
        if not rows:
            return 0.0, 0.0
        years = max((rows[-1]["utc"] - rows[0]["utc"]) / (365.25 * 86400), 0.25)
        return eq ** (1 / years) - 1, dd

    # spring label (P4): inside the 4-bar compression window before the signal bar
    def spring(t):
        i = t["i"]; lo = D["l"]; cl = D["c"]; atr = D["atr"]
        for j in range(i - g.COMP_BARS + 1, i):
            prior = float(np.min(lo[i - g.COMP_BARS:j]))
            if lo[j] < prior - 0.3 * atr[j] and cl[j] > prior:
                return True
        return False

    def upthrust(t):
        i = t["i"]; hi = D["h"]; cl = D["c"]; atr = D["atr"]
        for j in range(i - g.COMP_BARS + 1, i):
            prior = float(np.max(hi[i - g.COMP_BARS:j]))
            if hi[j] > prior + 0.3 * atr[j] and cl[j] < prior:
                return True
        return False

    for t in base:
        t["spring"] = spring(t) if t["d"] == 1 else upthrust(t)

    groups = {
        "P1: mua cùng sóng D1": [t for t in base if t["d"] == 1 and t["wave"] == 1],
        "mua ngược sóng D1": [t for t in base if t["d"] == 1 and t["wave"] == -1],
        "mua mọi lệnh": [t for t in base if t["d"] == 1],
        "bán cùng sóng D1": [t for t in base if t["d"] == -1 and t["wave"] == 1],
        "bán mọi lệnh": [t for t in base if t["d"] == -1],
    }
    res = {"bars": n, "first": int(D["t"][0]), "last": int(D["t"][-1]), "trades": len(base), "groups": {}}
    for name, rows in groups.items():
        per = {p: [t["rh"] for t in rows if t["p"] == p] for p, _, _ in PER}
        per15 = {p: [t["rh15"] for t in rows if t["p"] == p] for p, _, _ in PER}
        tv = [t for t in rows if t["p"] in ("train", "validate")]
        res["groups"][name] = {
            "per": {p: cell(v) for p, v in per.items()},
            "per15": {p: cell(v) for p, v in per15.items()},
            "p_random_train_val": p_random(tv) if name.startswith("P1") or name == "mua mọi lệnh" else None,
            "sim": {f"{r*100:.2f}%": {p: sim([t for t in rows if t["p"] == p], r) for p in DECIDE} for r in (0.005, 0.0075)}
            if name.startswith("P1") else None,
        }

    # P4 label comparison on the P1 book and on every H1 buy
    def label_block(rows):
        out = {}
        for p in DECIDE + ("sớm", "07/2026+"):
            a = [t["rh"] for t in rows if t["p"] == p and t["spring"]]
            b = [t["rh"] for t in rows if t["p"] == p and not t["spring"]]
            out[p] = {"label": cell(a), "nolabel": cell(b),
                      "diff": (float(np.mean(a)) - float(np.mean(b))) if a and b else None}
        pool = [t for t in rows if t["p"] in DECIDE]
        lab = np.array([t["spring"] for t in pool]); r = np.array([t["rh"] for t in pool])
        if lab.sum() and (~lab).sum():
            actual = r[lab].mean() - r[~lab].mean()
            hits = 0
            for _ in range(PERMS):
                sh = np.random.permutation(lab)
                hits += (r[sh].mean() - r[~sh].mean()) >= actual
            out["perm_p"] = (hits + 1) / (PERMS + 1)
            out["share"] = float(lab.mean())
        return out

    res["p4_p1_book"] = label_block(groups["P1: mua cùng sóng D1"])
    res["p4_all_buys"] = label_block(groups["mua mọi lệnh"])
    res["p4_sells_upthrust"] = label_block(groups["bán mọi lệnh"])
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
