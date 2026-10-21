"""G138 PRELIMINARY (diagnostic, no decision cells): why the D1 SMA50/SMA200 filter of G134/G135 does not show on the VPS
Lirunex bars. Sensitivity of "with / against the D1 state" by day boundary, timeframe and period.

Books: the S07 M30 book (G89 port, as g136_prelim_p1m30) and plain G67 S07 trades (B6, E2X, TP 8, harsh) on M30 / H1 / H4.
D1 state = sign(SMA50 - SMA200) of the daily closes of the M30 bars, last day CLOSED before the entry.
Day definitions: server midnight (G134/G135 and the EA's broker D1 bars on Lirunex: 5 days a week), UTC 00:00 and UTC 12:00
(6 "days" a week: a short Sunday bin), UTC 00:00 with Sunday merged into Monday (boundary only), server days with SMA 42/167
(length only: the calendar span of 50/200 six-day bins), and server with one extra day of lag.

Usage: g138_d1_sensitivity.py <a "data" dir with m30v/ m15v/ h1v/ h4v/ XAUUSD.csv> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g136_prelim_p1m30 as p1  # noqa: E402

PERIODS = {
    "G136": [("sớm 06/2019–06/2021", g.ts(2019, 6, 1), g.ts(2021, 7, 1)), ("train 07/2021–2023", g.ts(2021, 7, 1), g.ts(2024, 1, 1)),
             ("validate 2024–06/2025", g.ts(2024, 1, 1), g.ts(2025, 7, 1)), ("test 07/2025–06/2026", g.ts(2025, 7, 1), g.ts(2026, 7, 1)),
             ("07/2026+", g.ts(2026, 7, 1), g.ts(2030, 1, 1))],
    "G135 (M30/H1)": [("train 09/2018–2023", g.ts(2018, 9, 1), g.ts(2024, 1, 1)), ("validate 2024–06/2025", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
                      ("test 07/2025–10/2026", g.ts(2025, 7, 1), g.ts(2026, 10, 10))],
    "năm": [(str(y), g.ts(y, 1, 1), g.ts(y + 1, 1, 1)) for y in range(2019, 2027)],
}
PERMS = 2000
np.random.seed(138)


def d1_states(D):
    """{boundary: f(entry_utc) -> state}; D = the M30 bars."""
    c, t, utc = D["c"], D["t"], D["utc"]
    uk = utc // 86400
    sunday_to_monday = uk + ((uk + 3) % 7 == 6)                            # (day + 3) % 7: Monday 0 ... Sunday 6
    specs = {"server 00:00": (t // 86400, 50, 200), "UTC 00:00": (uk, 50, 200), "UTC 12:00": ((utc - 43200) // 86400, 50, 200),
             "UTC 00:00, gộp Chủ nhật vào thứ Hai": (sunday_to_monday, 50, 200),
             "server 00:00, SMA 42/167 (độ dài như 6 ngày/tuần)": (t // 86400, 42, 167)}
    out = {}
    for name, (key, n1, n2) in specs.items():
        ends = np.r_[np.nonzero(np.diff(key))[0], len(key) - 1]
        k, lc = key[ends], c[ends]
        s50 = np.convolve(lc, np.ones(n1) / n1, "full")[:len(lc)]
        s200 = np.convolve(lc, np.ones(n2) / n2, "full")[:len(lc)]
        st = np.where(np.arange(len(lc)) >= n2 - 1, np.sign(s50 - s200), 0).astype(int)

        def f(u, key=key, k=k, st=st, lag=0):
            j = int(np.searchsorted(utc, u, side="right")) - 1                 # bar holding the entry
            q = int(np.searchsorted(k, key[max(j, 0)], side="left")) - 1 - lag
            return int(st[q]) if q >= 0 else 0
        out[name] = f
        if name == "server 00:00":
            out["server, trễ thêm 1 ngày"] = lambda u, f=f: f(u, lag=1)
    return out


def summarize(rows, states):
    res = {}
    for b in states:
        res[b] = {}
        for pname, plist in PERIODS.items():
            tab = {}
            for n, a, z in plist:
                cellrow = {}
                for side, dd in (("mua", 1), ("bán", -1), ("cả hai", 0)):
                    s = [x for x in rows if a <= x["u"] < z and (dd == 0 or x["d"] == dd)]
                    w = [x["r"] for x in s if x["st"][b] == x["d"]]
                    ag = [x["r"] for x in s if x["st"][b] == -x["d"]]
                    cellrow[side] = {"cùng": f"{len(w)} / {np.mean(w):+.3f}" if w else "—",
                                     "ngược": f"{len(ag)} / {np.mean(ag):+.3f}" if ag else "—",
                                     "chênh": round(float(np.mean(w) - np.mean(ag)), 3) if w and ag else None}
                tab[n] = cellrow
            res[b][pname] = tab
        # permutation p (one-sided: with > against), buys and sells pooled, legs with a known state, 07/2021-06/2026
        pool = [x for x in rows if g.ts(2021, 7, 1) <= x["u"] < g.ts(2026, 7, 1) and x["st"][b] != 0]
        lab = np.array([x["st"][b] == x["d"] for x in pool]); r = np.array([x["r"] for x in pool])
        if lab.sum() and (~lab).sum():
            act = r[lab].mean() - r[~lab].mean()
            hits = sum((r[s].mean() - r[~s].mean()) >= act for s in (np.random.permutation(lab) for _ in range(PERMS)))
            res[b]["p hoán vị 07/2021–06/2026 (cùng > ngược)"] = round((hits + 1) / (PERMS + 1), 4)
            res[b]["chênh 07/2021–06/2026"] = round(float(act), 3)
    return res


def plain(tf, root, comp, cool, hold):
    g.set_tf(tf)
    g.DATA = root / f"{tf.lower()}v"
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = comp, cool, hold
    D = g.load("XAUUSD")
    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    out = []
    for t in g.trades("XAUUSD", "E2X", 8.0, None, sig):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        out.append(dict(d=t["d"], u=int(D["utc"][t["e0"]]), r=h.harsh(t, D)))
    return out


def main():
    root = Path(sys.argv[1])
    g.HERE = root.parent
    g.set_tf("M30")
    states = d1_states(g.load("XAUUSD"))
    books = {"S07 M30 sổ G89 (mọi chân)": [dict(d=x["d"], u=x["ein"], r=x["r"]) for x in p1.m30_book()]}
    for tf, cfg in (("M30", (8, 4, 240)), ("H1", (4, 2, 120)), ("H4", (8, 4, 240))):
        books[f"S07 G67 {tf}"] = plain(tf, root, *cfg)
    res = {}
    for name, rows in books.items():
        for x in rows:
            x["st"] = {b: f(x["u"]) for b, f in states.items()}
        flips = {b: round(float(np.mean([x["st"][b] != x["st"]["server 00:00"] for x in rows])), 4) for b in states}
        res[name] = {"số lệnh": len(rows), "tỷ lệ đổi trạng thái so với server": flips, **summarize(rows, states)}
        print(name, len(rows), flips, flush=True)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
