"""G136 PRELIMINARY: P1 in full (H1 with-wave buys, no overlap with an open S07 M30 buy leg, portfolio MAR / DD
against M30 alone) and P4 on the M30 book, on the VPS Lirunex bars (EEA_ExportDeals M30 / M15, research H1 / H4).

Not the plan's data source; not for decisions. The M30 book is the G89 Python port of S07Tester (base, early,
re-entry, adds) rebuilt on these bars: M30 sub-bars until 09/2022, M15 sub-bars and M15 adds after (M15 export
starts 08/2022).
Usage: g136_prelim_p1m30.py <a "data" dir with m30v/ m15v/ h1v/ h4v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g89_full_book as fb  # noqa: E402
from g134_extensions import CAP0, YEAR, sim  # noqa: E402

PER = [("train", g.ts(2021, 7, 1), g.ts(2024, 1, 1)), ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
       ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1))]
EXTRA = [("sớm", g.ts(2019, 6, 1), g.ts(2021, 7, 1)), ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
RUNS, PERMS = 200, 2000
random.seed(136)
np.random.seed(136)


def period(u, table=PER + EXTRA):
    for n, a, z in table:
        if a <= u < z:
            return n
    return None


def cell(rs):
    s = g.stats(list(rs))
    return f"{s['n']} / {s['exp']:+.3f} / {s['total']:+.1f}" if s["n"] else "—"


def d1_from(tf):
    g.set_tf(tf)
    D = g.load("XAUUSD")
    day = D["t"] // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    lc = D["c"][ends]
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    st = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0)
    days = day[ends]
    return lambda srv: int(st[q]) if (q := np.searchsorted(days, srv // 86400, side="left") - 1) >= 0 else 0


def m30_book():
    fb.SPLIT = g.ts(2022, 9, 1)
    fb.START = g.ts(2019, 6, 1)
    legs = []
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            ctx = fb.e73.context(main, sub)
            bases += fb.base_book(ctx, d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                w = (1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD
                legs.append(dict(d=d, ein=int(L["ein"]), eout=int(L["eout"]), srv=int(L["srv_in"]), r=float(L["rh"]),
                                 w=w, base=j == 0, kind=L.get("kind", "ADD")))
    return legs


def main():
    root = Path(sys.argv[1])
    g.HERE = root.parent                                             # set_tf reads HERE / "data" / "<tf>v"
    d1 = d1_from("M30")
    legs = m30_book()
    for x in legs:
        x["aligned"] = d1(x["srv"]) == x["d"]
    m30 = [dict(t_in=x["ein"], t_out=x["eout"], r=x["r"], risk=0.015 * x["w"] * (1.0 if x["aligned"] else 0.5))
           for x in legs]

    # --- H1 book (G135 H1 settings)
    g.set_tf("H1")
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = 4, 2, 120
    D = g.load("XAUUSD")
    n = len(D["t"])

    def finish(t):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        t["rh"] = h.harsh(t, D)
        t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
        t["ein"], t["eout"] = int(D["utc"][t["e0"]]), int(D["utc"][t["x"]])
        t["p"] = period(t["utc"])
        t["wave"] = d1(int(D["t"][t["i"]])) * t["d"]
        t["ovl"] = any(x["d"] == t["d"] and x["ein"] <= t["ein"] < x["eout"] for x in legs)
        return t

    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    h1 = [finish(t) for t in g.trades("XAUUSD", "E2X", 8.0, None, sig)]
    h1 = [t for t in h1 if t["p"]]
    p1 = [t for t in h1 if t["d"] == 1 and t["wave"] == 1 and not t["ovl"]]
    p1_ovl = [t for t in h1 if t["d"] == 1 and t["wave"] == 1 and t["ovl"]]

    by_hour = {}
    for j in range(250, n - 2):
        p = period(int(D["utc"][j]))
        if p:
            by_hour.setdefault((p, int(D["t"][j] % 86400 // 3600)), []).append(j)

    def p_random(rows):
        actual = float(np.mean([t["rh"] for t in rows]))
        hits = 0
        for _ in range(RUNS):
            out = []
            for t in rows:
                pool = by_hour.get((t["p"], int(D["t"][t["i"]] % 86400 // 3600)), [])
                for _ in range(50):
                    r = g.walk(D, random.choice(pool), t["d"], "E2X", 8.0, None)
                    if r is not None:
                        r["srv_in"], r["srv_out"] = int(D["t"][r["e0"]]), int(D["t"][r["x"]])
                        out.append(h.harsh(r, D)); break
            hits += float(np.mean(out)) >= actual
        return (hits + 1) / (RUNS + 1)

    def dd_p90(book):
        a, out = g.ts(2021, 7, 1), []
        while a + YEAR <= g.ts(2026, 7, 1) + 1:
            out.append(sim(book, a, int(a + YEAR))[1])
            a += 30 * 86400
        return float(np.percentile(out, 90))

    res = {"m30_legs": len(legs), "m30_aligned_share": float(np.mean([x["aligned"] for x in legs])),
           "p1": {}, "portfolio": {}}
    for name, rows, key in (("P1 (mua cùng sóng, không trùng M30)", p1, "rh"), ("P1 phí ×1,5", p1, "rh15"),
                            ("mua cùng sóng nhưng TRÙNG M30 (bị loại)", p1_ovl, "rh"),
                            ("mọi lệnh mua H1", [t for t in h1 if t["d"] == 1], "rh")):
        res["p1"][name] = {p: cell(t[key] for t in rows if t["p"] == p) for p, _, _ in PER + EXTRA}
    tv = [t for t in p1 if t["p"] in ("train", "validate")]
    res["p1"]["p ngẫu nhiên (train+validate)"] = p_random(tv)
    res["p1"]["tỷ lệ mua cùng sóng bị loại vì trùng M30"] = len(p1_ovl) / max(len(p1) + len(p1_ovl), 1)

    books = {"M30 một mình": m30}
    for r in (0.005, 0.0075):
        books[f"M30 + H1 {r*100:.2f}%"] = m30 + [dict(t_in=t["ein"], t_out=t["eout"], r=t["rh"], risk=r) for t in p1]
        books[f"H1 một mình {r*100:.2f}%"] = [dict(t_in=t["ein"], t_out=t["eout"], r=t["rh"], risk=r) for t in p1]
    for name, book in books.items():
        row = {p: [round(v, 4) if isinstance(v, float) else v for v in sim(book, a, b)] for p, a, b in PER}
        row["dd_p90_1y"] = round(dd_p90(book), 4)
        res["portfolio"][name] = row

    # --- P4 on the M30 book: spring / upthrust in the 8-bar compression window before the signal bar
    g.set_tf("M30")
    P = g.load("XAUUSD")

    def label(x):
        i = int(np.searchsorted(P["t"], x["srv"] - 1800, side="right")) - 1     # last M30 bar closed at entry
        lo, hi, cl, atr = P["l"], P["h"], P["c"], P["atr"]
        for j in range(i - 7, i):
            if x["d"] == 1:
                prior = float(np.min(lo[i - 8:j]))
                if lo[j] < prior - 0.3 * atr[j] and cl[j] > prior:
                    return True
            else:
                prior = float(np.max(hi[i - 8:j]))
                if hi[j] > prior + 0.3 * atr[j] and cl[j] < prior:
                    return True
        return False

    def label_block(rows):
        out = {}
        for p, _, _ in PER + EXTRA:
            a = [x["r"] for x in rows if period(x["ein"]) == p and x["lab"]]
            b = [x["r"] for x in rows if period(x["ein"]) == p and not x["lab"]]
            out[p] = {"label": cell(a), "nolabel": cell(b),
                      "diff": round(float(np.mean(a)) - float(np.mean(b)), 3) if a and b else None}
        pool = [x for x in rows if period(x["ein"], PER)]
        lab = np.array([x["lab"] for x in pool]); r = np.array([x["r"] for x in pool])
        if lab.sum() and (~lab).sum():
            actual = r[lab].mean() - r[~lab].mean()
            hits = sum((r[s].mean() - r[~s].mean()) >= actual for s in (np.random.permutation(lab) for _ in range(PERMS)))
            out["perm_p"] = (hits + 1) / (PERMS + 1)
            out["share"] = float(lab.mean())
        return out

    bases = [x for x in legs if x["base"]]
    for x in bases:
        x["lab"] = label(x)
    res["p4_m30_buys"] = label_block([x for x in bases if x["d"] == 1])
    res["p4_m30_sells"] = label_block([x for x in bases if x["d"] == -1])
    res["m30_base_by_period"] = {d: {p: cell(x["r"] for x in bases if x["d"] == d and period(x["ein"]) == p)
                                     for p, _, _ in PER + EXTRA} for d in (1, -1)}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
