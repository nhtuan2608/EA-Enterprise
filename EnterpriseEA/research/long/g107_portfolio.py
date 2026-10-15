"""G107: one 10,000 USD account running S07Tester + XauRegimeTester + CtxLimitTester at once (Python ports).

User (11/10): the three bots with their latest sets on one 10k account, no trade limit between them; combined
balance / equity curve.

  python g107_portfolio.py

Bots (risk on the initial 10,000, no compounding, like InpRiskBase=INITIAL):
  S07   S07Tester full family (G89 port: base S07/S07S, early, re-entry, adds), 1.5% x weight; harsh G68 costs
  XRT   XauRegimeTester set A (D1 EMA50 + 10-day slope, buy only, market at the open, stop 3 ATR20 D1,
        exit when the regime turns off or a D1 close 3 ATR below the best close), 1.5%; spread 0.30 USD
  BOX   CtxBoxTester M30 (G106: context switch on, BOX hold on H4, buy and sell, one per side), 1.5%; bar spread
  CTX   CtxLimitTester gold_limit (MKT04 plan L with the S07 gates and weights; walk-forward forecasts, so every
        trade from 2020 is out of sample for its model), 0.5% x weight
Window: 2020-01-01 .. 2026-10-09 (CTX forecasts start 2020). Equity marks open S07 and XRT positions at bar closes;
CTX positions (<= 48 h, 0.5%) are booked at their exit.
Out: docs/superpowers/reports/img/g107_portfolio.png and the summary printed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "markets"))

START, END = pd.Timestamp("2020-01-01"), pd.Timestamp("2026-10-10")
CAPITAL = 10_000.0
IMG = HERE.parents[1] / "docs" / "superpowers" / "reports" / "img"


# ------------------------------------------------------------------------------------------------- S07
def s07_legs():
    import g89_full_book as fb
    rows = []
    for d in (1, -1):
        bases = []
        for main, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            ctx = fb.e73.context(main, sub)
            bases += fb.base_book(ctx, d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                w = (1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD
                rows.append(dict(bot="S07", d=d, t_in=pd.to_datetime(L["ein"], unit="s"),
                                 t_out=pd.to_datetime(L["eout"], unit="s"), r=L["rh"], money=CAPITAL * 0.015 * w,
                                 U=pd.to_datetime(L["U"], unit="s"), C=np.asarray(L["C"]), entry=L["entry"],
                                 risk=L["risk"]))
    return rows


# ------------------------------------------------------------------------------------------------- XRT
def xrt_legs():
    from g96_regime import load_d1, r1
    d = load_d1()
    st = np.nan_to_num(r1(d, 50))
    o, h, l, c, a, day = (d[k].to_numpy() for k in ("open", "high", "low", "close", "atr", "day"))
    rows, pos, blocked = [], None, 0
    for t in range(1, len(d)):
        if pos is not None:
            exit_px = None
            if o[t] <= pos["stop"]:
                exit_px = o[t]
            elif pos["exit_next"]:
                exit_px = o[t]
            elif l[t] <= pos["stop"]:
                exit_px = pos["stop"]
            if exit_px is not None:
                pos["t_out"] = pd.Timestamp(day[t])
                pos["r"] = (exit_px - pos["entry"] - 0.30) / pos["risk"]
                pos["U"] = pd.to_datetime(pos["U"]); pos["C"] = np.asarray(pos["C"])
                rows.append(pos)
                pos = None
            else:
                pos["U"].append(day[t]); pos["C"].append(c[t])
                pos["best"] = max(pos["best"], c[t])
                if st[t] != 1:
                    pos["exit_next"] = True
                elif pos["best"] - c[t] >= 3 * a[t]:
                    pos["exit_next"] = True
                    blocked = 1
                continue
        if blocked and st[t - 1] != 1:
            blocked = 0
        if st[t - 1] == 1 and not blocked and np.isfinite(a[t - 1]) and pos is None:
            risk = 3 * a[t - 1]
            pos = dict(bot="XRT", d=1, t_in=pd.Timestamp(day[t]), entry=o[t], risk=risk, stop=o[t] - risk,
                       best=c[t], exit_next=False, money=CAPITAL * 0.015, U=[day[t]], C=[c[t]])
            if l[t] <= pos["stop"]:
                pos.update(t_out=pd.Timestamp(day[t]), r=-1.0, U=pd.to_datetime(pos["U"]), C=np.asarray(pos["C"]))
                rows.append(pos)
                pos = None
            elif st[t] != 1:
                pos["exit_next"] = True
    return rows


# ------------------------------------------------------------------------------------------------- BOX
def box_legs(tf="M30"):
    """CtxBoxTester (G106): context switch on + BOX hold on the higher TF, buy and sell, 1.5%, one per side."""
    import g106_ctx_box as gb
    m = gb.load(tf)
    S = gb.Sim(m)
    ts = m["ts"].to_numpy()
    rows = []
    for d in (-1, 1):
        ctx = gb.context(m, d)
        sw = ctx & ~np.concatenate([[False], ctx[:-1]])
        free = 0
        for i in np.flatnonzero(sw):
            if i < free:
                continue
            res = S.run(i, d)
            if res is None:
                continue
            r, jx, why = res
            entry = S.o[i + 1] + (S.sp[i + 1] if d == 1 else 0.0)
            stop = (S.ll16[i] - 0.1 * S.atr[i]) if d == 1 else (S.hh16[i] + 0.1 * S.atr[i])
            rows.append(dict(bot="BOX", d=d, t_in=pd.Timestamp(ts[i]), t_out=pd.Timestamp(ts[jx]), r=r,
                             money=CAPITAL * 0.015, U=pd.to_datetime(ts[i + 1:jx + 1]), C=S.c[i + 1:jx + 1],
                             entry=entry, risk=d * (entry - stop)))
            free = jx + 1
    return rows


# ------------------------------------------------------------------------------------------------- CTX
def ctx_legs():
    import mkt03_context as m3
    import mkt04_context_h4 as m4
    import mkt04_gold_s07_gates as gg
    g = m4.GROUPS["Vàng"]
    F = m4.build_group("Vàng", g)
    m3.walk_forward(F, g)
    F = F.merge(gg.gates(), on="time", how="left")
    F["atr"] = (F["c"] - F["e21"]) / F["d_e21"]
    v0 = m3.ts(*g["oos"])
    vp = pd.concat([F.loc[(F["time"] >= v0) & (F["time"] < m3.TEST0), f"P_L_{s}"] for s in ("p", "n")]).dropna()
    th = float(vp.quantile(gg.THETA_Q["L"]))
    tr = gg.simulate(F, "L", th, v0, m3.TEST1, "gate")
    by_i = dict(zip(F["i"], F["time"]))
    rows = []
    for x in tr:
        rows.append(dict(bot="CTX", d=x["d"], t_in=pd.to_datetime(x["t"], unit="s"),
                         t_out=pd.to_datetime(x["t"], unit="s") + pd.Timedelta(hours=24), r=x["r"],
                         money=CAPITAL * 0.005 * x["w"], U=None, C=None, entry=None, risk=None))
    print(f"CTX threshold {th:+.3f}, trades {len(rows)}")
    return rows


def curves(legs):
    days = pd.date_range(START, END, freq="D")
    realized = {b: np.zeros(len(days)) for b in ("S07", "XRT", "CTX", "BOX")}
    openpnl = np.zeros(len(days))
    for L in legs:
        if L["t_out"] < START or L["t_in"] >= END:
            continue
        k = days.searchsorted(L["t_out"].normalize())
        if k < len(days):
            realized[L["bot"]][k] += L["money"] * L["r"]
        if L["U"] is not None and len(L["U"]):
            s = pd.Series(L["C"], index=L["U"]).groupby(pd.DatetimeIndex(L["U"]).normalize()).last()
            s = s[(s.index >= START) & (s.index < L["t_out"].normalize())]
            if len(s):
                mtm = L["money"] * L["d"] * (s.to_numpy() - L["entry"]) / L["risk"]
                idx = days.searchsorted(s.index)
                ok = idx < len(days)
                np.add.at(openpnl, idx[ok], mtm[ok])
    bal = {b: CAPITAL + np.cumsum(v) for b, v in realized.items()}
    total_real = sum(np.cumsum(v) for v in realized.values())
    balance = CAPITAL + total_real
    equity = balance + openpnl
    return days, balance, equity, bal


def stats(days, eq):
    s = pd.Series(eq, index=days)
    yrs = (days[-1] - days[0]).days / 365.25
    dd = (s.cummax() - s) / s.cummax()
    return dict(final=s.iloc[-1], cagr=(s.iloc[-1] / CAPITAL) ** (1 / yrs) - 1, maxdd=dd.max(),
                worst=s.min())


def main():
    legs = s07_legs() + xrt_legs() + ctx_legs() + box_legs("M30")
    legs = [L for L in legs if START <= L["t_in"] < END]
    days, balance, equity, per = curves(legs)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    IMG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    st = stats(days, equity)
    ax[0].plot(days, equity, color="#2a6fdb", lw=1.0, label=f"Equity chung (cuối {equity[-1]:,.0f} USD)")
    ax[0].plot(days, balance, color="#1b1b1b", lw=1.4, label=f"Balance chung (cuối {balance[-1]:,.0f} USD)")
    colors = {"S07": "#e07b00", "XRT": "#2e9d57", "CTX": "#9b4dca", "BOX": "#c2185b"}
    names = {"S07": "S07Tester", "XRT": "XauRegimeTester", "CTX": "CtxLimitTester", "BOX": "CtxBoxTester M30"}
    for b, v in per.items():
        ax[0].plot(days, v, color=colors[b], lw=0.9, alpha=0.85, label=f"{names[b]} riêng (cuối {v[-1]:,.0f})")
    ax[0].axhline(CAPITAL, color="#999", lw=0.6, ls="--")
    ax[0].set_ylabel("USD")
    ax[0].set_title(f"4 bot trên một tài khoản 10.000 USD, XAUUSD, 01/2020 – 10/2026 · "
                    f"{st['cagr'] * 100:+.0f}%/năm, sụt equity lớn nhất {st['maxdd'] * 100:.0f}%")
    ax[0].legend(loc="upper left", fontsize=9)
    ax[0].grid(alpha=0.3)
    eqs = pd.Series(equity, index=days)
    ax[1].fill_between(days, -(eqs.cummax() - eqs) / eqs.cummax() * 100, 0, color="#d64545", alpha=0.5)
    ax[1].set_ylabel("Sụt equity %")
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    out = IMG / "g107_portfolio_4bots.png"
    fig.savefig(out, dpi=130)
    print("saved", out)
    print("combined:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()})
    for b in per:
        x = [L for L in legs if L["bot"] == b]
        r = np.array([L["r"] for L in x]); mny = np.array([L["money"] * L["r"] for L in x])
        s = stats(days, per[b])
        print(f"{names[b]}: trades {len(x)}, R/trade {r.mean():+.3f}, profit {mny.sum():+,.0f} USD, "
              f"own maxDD {s['maxdd'] * 100:.1f}%")
    yr = pd.Series(equity, index=days).resample("YE").last()
    prev = pd.concat([pd.Series([CAPITAL]), yr.iloc[:-1].reset_index(drop=True)])
    print("by year (equity end, % of start):", {d.year: (round(v), f"{(v / p - 1) * 100:+.0f}%")
                                               for d, v, p in zip(yr.index, yr.to_numpy(), prev.to_numpy())})


if __name__ == "__main__":
    main()
