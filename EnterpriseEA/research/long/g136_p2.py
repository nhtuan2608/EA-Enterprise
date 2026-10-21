"""G136 P2 OFFICIAL RUN (amended rule of 21/10/2026, PC research data XAUUSD-VIP): the EA's S07 sell family only on D1
death-cross days.

Decision book (plan): the EA sell rules on M30, i.e. the G89 Python port with its defaults (S07S base with the L2 location,
S07ES early, S07RS re-entry, S07AS adds M15 / H1 / H4; M15 sub-bars and M15 adds from 2021-07-20). Every leg counts as one
trade (R per leg, harsh costs). D1 state = sign(SMA50 - SMA200) of the server-day closes of the M30 bars, last day CLOSED
before the leg's entry (the EA's broker D1 bars: 5 a week, see the G138 PC report).

  D0  every sell leg 01/2018-12/2023          DX  the ones on death-cross days (decision cell)
  halves: entries before / from 07/2021      golden 2018-2026 (report)      forward from 26/06/2026; clean from 21/10/2026
Random control (death-cross days 01/2018-12/2023 only, 200 runs): for each DX leg a random M30 bar of the same server hour,
sell at the next open with the leg's stop distance in M30 ATR, exits of the base leg (fb.walk on M30: SL, 8R, EMA55/100
close, ADX exhaustion, 240 bars), harsh costs. Adds exit differently in the book (E2X on their own frame); the control
uses one exit model for every leg, as the preliminary H1/H4 control did.
Reference (not the decision): the preliminary G67 S07 sells on H1 / H4 (g136_prelim_p2.run_tf) and an approximation of
the EA's standalone S07AS (InpS07AsStandalone): H1 / H4 add signals with the ordered ribbon, on death-cross days, with no
sell leg of the M30 book open; sentiment is not modelled.

Usage: g136_p2.py <data dir with m30v/ m15v/ h1v/ h4v/ XAUUSD.csv> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g89_full_book as fb  # noqa: E402
import g136_prelim_p2 as pre  # noqa: E402

SEL0, SEL_END, HALF = g.ts(2018, 1, 1), g.ts(2024, 1, 1), g.ts(2021, 7, 1)
FWD, FWD_CLEAN = g.ts(2026, 6, 26), g.ts(2026, 10, 21)
RUNS = 200
random.seed(136)


def cell(rs):
    rs = list(rs)
    return {"n": len(rs), "exp": round(float(np.mean(rs)), 3), "total": round(float(np.sum(rs)), 1)} if rs else {"n": 0}


def d1_state():
    g.set_tf("M30")
    D = g.load("XAUUSD")
    day = D["t"] // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], len(day) - 1]
    lc, days = D["c"][ends], day[ends]
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    st = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0).astype(int)

    def f(srv):
        q = int(np.searchsorted(days, srv // 86400, side="left")) - 1
        return int(st[q]) if q >= 0 else 0
    return f


def sell_book():
    d = -1
    bases = []
    for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
        bases += fb.base_book(fb.e73.context(main, sub), d, t0, t1, early=True, re=True)
    pool = fb.add_pool(d)
    legs = []
    for cl in fb.attach_adds(bases, pool):
        for j, L in enumerate(cl):
            kind = L.get("kind", "S07S") if j == 0 else "S07AS-" + L["tf"]
            legs.append(dict(kind=kind, ein=int(L["ein"]), eout=int(L["eout"]), srv=int(L["srv_in"]), r=float(L["rh"]),
                             r15=float(L["r"] - 1.5 * (L["r"] - L["rh"])), risk=float(L["risk"]), base=j == 0))
    return legs, pool


def main():
    root = Path(sys.argv[1])
    g.HERE = root.parent
    d1 = d1_state()
    legs, pool = sell_book()
    for x in legs:
        x["st"] = d1(x["srv"])
    sel = [x for x in legs if SEL0 <= x["ein"] < SEL_END]
    dx = [x for x in sel if x["st"] == -1]

    # random control on death-cross days, M30 bars, base-leg exits
    ctx = fb.e73.context("M30", "M30")
    P, S = ctx["P"], ctx["S"]
    n = len(S["t"])
    hours = {}
    for j in range(450, n - 2):
        u = int(S["utc"][j])
        if SEL0 <= u < SEL_END and d1(int(S["t"][j])) == -1:
            hours.setdefault(int(S["t"][j] % 86400 // 3600), []).append(j)
    allj = [j for v in hours.values() for j in v]
    for x in dx:
        k = int(np.searchsorted(S["utc"], x["ein"], side="right")) - 1
        x["k_atr"] = x["risk"] / float(P["atr"][max(k - 1, 0)])
        x["hour"] = int((x["srv"]) % 86400 // 3600)

    def rand_mean():
        out = []
        for x in dx:
            cands = hours.get(x["hour"]) or allj
            for _ in range(50):
                j = random.choice(cands)
                e = j + 1
                dist = x["k_atr"] * float(P["atr"][j])
                if dist <= 0:
                    continue
                t = fb.walk(ctx, e, float(S["o"][e]), -1, dist)
                if t is not None:
                    out.append(t["rh"]); break
        return float(np.mean(out))

    actual = float(np.mean([x["r"] for x in dx])) if dx else float("nan")
    p = (sum(rand_mean() >= actual for _ in range(RUNS)) + 1) / (RUNS + 1) if dx else None

    sells_fwd = [x for x in legs if x["ein"] >= FWD and x["st"] == -1]
    res = {
        "sổ bán M30 (mọi chân)": len(legs),
        "D0 bán 2018-2023": cell(x["r"] for x in sel),
        "DX bán death 2018-2023": cell(x["r"] for x in dx),
        "DX phí x1.5": cell(x["r15"] for x in dx),
        "DX nửa đầu (01/2018-06/2021)": cell(x["r"] for x in dx if x["ein"] < HALF),
        "DX nửa sau (07/2021-2023)": cell(x["r"] for x in dx if x["ein"] >= HALF),
        "DX theo loại": {k: cell(x["r"] for x in dx if x["kind"].split("-")[0] == k) for k in ("S07S", "S07ES", "S07RS", "S07AS")},
        "D0 theo loại": {k: cell(x["r"] for x in sel if x["kind"].split("-")[0] == k) for k in ("S07S", "S07ES", "S07RS", "S07AS")},
        "p ngẫu nhiên (ngày death)": p,
        "bán golden 2018-2026": cell(x["r"] for x in legs if x["st"] == 1 and SEL0 <= x["ein"] < FWD),
        "bán golden 2024-06/2026": cell(x["r"] for x in legs if x["st"] == 1 and SEL_END <= x["ein"] < FWD),
        "forward bán death từ 26/06/2026 (dữ liệu tới)": cell(x["r"] for x in sells_fwd if x["ein"] < FWD_CLEAN),
        "forward kín từ 21/10/2026": cell(x["r"] for x in sells_fwd if x["ein"] >= FWD_CLEAN),
        "chân cuối của dữ liệu (utc)": max(x["ein"] for x in legs),
    }
    # approximate standalone S07AS: H1 / H4 add signals, ordered ribbon at the signal bar, death-cross day,
    # no sell leg of the M30 book open at the entry, one at a time
    sa = []
    for tf in ("H1", "H4"):
        g.set_tf(tf)
        D = g.load("XAUUSD")
        E = D["E"]
        for t in [t for t in pool if t["tf"] == tf]:
            i = t["i"]
            ordd = E[21][i] < E[55][i] < E[100][i] and D["c"][i] < E[21][i]
            if not ordd or d1(int(t["srv_in"])) != -1:
                continue
            if any(x["ein"] <= t["ein"] < x["eout"] for x in legs):
                continue
            sa.append(dict(ein=int(t["ein"]), eout=int(t["eout"]), r=float(t["rh"]), tf=tf))
    sa.sort(key=lambda z: z["ein"])
    sa1, free = [], 0
    for z in sa:
        if z["ein"] >= free:
            sa1.append(z); free = z["eout"]
    res["S07AS đứng độc lập (xấp xỉ, báo cáo)"] = {
        "2018-2023": cell(z["r"] for z in sa1 if SEL0 <= z["ein"] < SEL_END),
        "2024-06/2026": cell(z["r"] for z in sa1 if SEL_END <= z["ein"] < FWD),
        "từ 26/06/2026": cell(z["r"] for z in sa1 if z["ein"] >= FWD),
        "theo khung 2018-2026": {tf: cell(z["r"] for z in sa1 if z["tf"] == tf) for tf in ("H1", "H4")}}
    # reference: preliminary G67 sells on H1 / H4 (same script as the VPS run)
    res["tham khảo G67 H1/H4"] = {tf: pre.run_tf(tf, *cfg, root) for tf, cfg in pre.TFS.items()}
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "tham khảo G67 H1/H4"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
