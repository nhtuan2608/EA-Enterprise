"""G136 PRELIMINARY P3: the VHedge V-candle family on M30 / M15 with morning / evening star signals, on the VPS
Lirunex bars (EEA_ExportDeals M30 from 03/2019, M15 from 08/2022). Not the plan's data source; not for decisions.

Context (G118 candidate A, at the signal bar): EMA21/55/100 fanned against the signal, ADX < 25, EMA200 slope
(48 bars) against the signal. V = G116/G118 V candle (signal = its close side of the EMA200). MS = morning star
(buy) / evening star (sell) with a touch or cross of the EMA200 in the 3 bars before the third candle.
Management: G116 hedge, stops +-2 ATR (G117 "A2"), result in U. Spread floored at its median (x1.5 variant).
Usage: g136_prelim_p3.py <a "data" dir with m30v/ m15v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g116_v_hedge as g116  # noqa: E402
import g118_v_combos as g118  # noqa: E402
from g117_v_filters import Sim2  # noqa: E402
from g134_extensions import prep_v  # noqa: E402

PER = [("sớm", "2019-06-01", "2021-07-01"), ("train", "2021-07-01", "2024-01-01"), ("validate", "2024-01-01", "2025-07-01"),
       ("test", "2025-07-01", "2026-07-01"), ("07/2026+", "2026-07-01", "2030-01-01")]
DECIDE = ("train", "validate", "test")
RUNS = 200
random.seed(136)


def period(ts):
    for n, a, z in PER:
        if pd.Timestamp(a) <= ts < pd.Timestamp(z):
            return n
    return None


def context(m, k, s):
    """Fan against s, ADX < 25 and EMA200 slope against s, all at bar k."""
    e21, e55, e100, e200, a, adx = (m[c].to_numpy() for c in ("e21", "e55", "e100", "e200", "atr", "adx"))
    fan = 1 if e21[k] > e55[k] > e100[k] else (-1 if e21[k] < e55[k] < e100[k] else 0)
    lb = min(48, k - 1)
    slope = (e200[k] - e200[k - lb]) / a[k]
    return fan == -s and adx[k] < 25 and np.sign(slope) == -s


def star(m, k):
    """+1 morning star, -1 evening star ending at bar k, else 0."""
    o, c, a = m["open"].to_numpy(), m["close"].to_numpy(), m["atr"].to_numpy()
    b1, b2, b3 = c[k - 2] - o[k - 2], c[k - 1] - o[k - 1], c[k] - o[k]
    mid1 = 0.5 * (o[k - 2] + c[k - 2])
    if abs(b2) > 0.3 * a[k] or abs(b1) < 0.6 * a[k] or abs(b3) < 0.5 * a[k]:
        return 0
    if b1 < 0 < b3 and c[k] > mid1:
        return 1
    if b3 < 0 < b1 and c[k] < mid1:
        return -1
    return 0


def touched(m, k):
    h, l, e = m["high"].to_numpy(), m["low"].to_numpy(), m["e200"].to_numpy()
    return any(l[i] <= e[i] <= h[i] for i in range(k - 3, k))


def run_tf(tf, root, start):
    m = pd.read_csv(root / tf / "XAUUSD.csv")
    m = prep_v(m)
    sp_raw = m["spread"].to_numpy() * 0.01
    med = float(np.median(sp_raw[sp_raw > 0]))
    out = {}
    n = len(m)
    first = m.index[m["ts"] >= pd.Timestamp(start)][0]

    groups_v = [(v, j) for v, j in g116.find_groups(m) if v >= first]
    F = g118.features(m, groups_v)
    keep = (F["fan_against"] & F["adx_lt25"] & F["slope_against"]).to_numpy() if len(F) else []
    V = [dict(v=v, j=j, s=int(F["vdir"].iat[q])) for q, (v, j) in enumerate(groups_v) if keep[q]]
    MS = []
    for k in range(max(first, 300), n - 3):
        s = star(m, k)
        if s and touched(m, k) and context(m, k, s):
            MS.append(dict(v=k, j=k, s=s))
    # random control pool: every bar with the MS context and an EMA200 touch, either side
    pool = {1: [], -1: []}
    for k in range(max(first, 300), n - 3):
        if touched(m, k):
            for s in (1, -1):
                if context(m, k, s):
                    pool[s].append(k)

    for mult, tag in ((1.0, ""), (1.5, " phí×1,5")):
        m["sp"] = np.maximum(sp_raw, med) * mult
        S = Sim2(m)

        def res(rows):
            for x in rows:
                x["u" + tag] = S.hedge_r(x["v"], x["j"], "A2")[0]
                x["p"] = period(m["ts"].iat[x["j"]])
            return rows

        res(V); res(MS)
        if not tag:
            # V u MS: one group per EMA200 touch - an MS within 6 bars after a kept V's return bar is the same touch
            vj = sorted(x["j"] for x in V)
            union = V + [x for x in MS if not any(0 <= x["j"] - j <= 6 for j in vj)]

            def p_random(rows):
                rows = [x for x in rows if x["p"] in ("train", "validate") and x["u"] == x["u"]]
                if not rows:
                    return None
                actual = float(np.mean([x["u"] for x in rows]))
                by = {}
                for s in (1, -1):
                    for k in pool[s]:
                        by.setdefault((period(m["ts"].iat[k]), s), []).append(k)
                hits = 0
                for _ in range(RUNS):
                    u = []
                    for x in rows:
                        cands = by.get((x["p"], x["s"]), [])
                        for _ in range(20):
                            r = S.hedge_r(*(2 * [random.choice(cands)]), "A2")[0]
                            if r == r:
                                u.append(r); break
                    hits += float(np.mean(u)) >= actual
                return (hits + 1) / (RUNS + 1)

        def cells(rows, key):
            o = {}
            for p, _, _ in PER:
                u = [x[key] for x in rows if x["p"] == p and x[key] == x[key]]
                o[p] = f"{len(u)} / {np.mean(u):+.3f} / {np.sum(u):+.1f}" if u else "—"
            return o

        for name, rows in (("V", V), ("MS", MS), ("V∪MS", union)):
            out[name + tag] = cells(rows, "u" + tag)
    out["p ngẫu nhiên MS (train+validate)"] = p_random(MS)
    out["p ngẫu nhiên V (train+validate)"] = p_random(V)
    out["MS trùng V (bỏ khỏi V∪MS)"] = len(MS) - (len(union) - len(V))
    out["MS mua / bán"] = [sum(x["s"] == 1 for x in MS), sum(x["s"] == -1 for x in MS)]
    out["bars"] = [str(m["ts"].iat[first]), str(m["ts"].iat[-1])]
    return out


def main():
    root = Path(sys.argv[1])
    res = {"M30": run_tf("m30v", root, "2019-06-01"), "M15": run_tf("m15v", root, "2022-09-01")}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
