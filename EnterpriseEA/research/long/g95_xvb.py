"""G95 part 2: XVB = box break in the volatility window, in the direction of the trend drift (XAUUSD, MT5 data).

User (11/10): no risk limits and no news filter yet; natural spread (the bar's own spread, no harsh costs);
find the most profitable scalp / swing form first, risk and news later.

  python g95_xvb.py

Periods: discovery 2024-05-14..2025-06-30 (selection), test 2025-07..2026-06 (opened once), examples 2026-07+.
Robustness: the same rules on M15 2021-07..2023 (quiet gold; box = 4 M15 bars).

Grid (all cells are reported):
  window  LDN  NY 03:00-05:00   |  NY  NY 08:00-11:00          (NY = server - 7 h)
  box     B60  the hour before the window  |  ASIA  NY 19:00 (prior day) .. 03:00
  width   W4   box <= 4 ATR (B60) / <= 12 ATR (ASIA)  |  WANY  no width limit
  trend   T0   both directions  |  TD  D1 side (close vs EMA50 D1, prior day)  |  TDA  D1 side and ADX14 D1 >= 20
  stop    SE   opposite box edge  |  SM  box middle
  exit    TP2 / TP3  fixed target, else close NY 16:00 (scalp)
          EOD  trail: close beyond EMA21 M15, at the latest NY 16:00 (scalp runner)
          SW   trail: close beyond EMA21 H1, at most 5 days (swing)
Entry: the first bar of the window that closes outside the box in an allowed direction; fill at the next bar
open; longs pay the spread of the entry bar (bars are bid), shorts pay the spread of the exit bar.
A bar touching both stop and target counts as the stop. One trade per window per day.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from g95_xau_read import DATA, atr

OUT = Path(__file__).resolve().parent / "out" / "g95"
DISC = ("2024-05-14", "2025-07-01")
TEST = ("2025-07-01", "2026-07-01")
EXAM = ("2026-07-01", "2027-01-01")
QUIET = ("2021-07-20", "2024-01-01")
WINDOWS = {"LDN": (3, 5), "NY": (8, 11)}


def d1_state() -> pd.DataFrame:
    d = pd.read_csv(DATA / "bars_XAUUSD_D1.csv")
    d["day"] = pd.to_datetime(d["time"], unit="s").dt.normalize()
    # the D1 export ends 10/2025: extend with server-day bars built from the M15 file (same broker clock)
    m = pd.read_csv(DATA / "m15v" / "XAUUSD.csv")
    m["day"] = pd.to_datetime(m["time"], unit="s").dt.normalize()
    m = m[m["day"] > d["day"].max()].groupby("day").agg(open=("open", "first"), high=("high", "max"),
                                                          low=("low", "min"), close=("close", "last")).reset_index()
    d = pd.concat([d[["day", "open", "high", "low", "close"]], m], ignore_index=True)
    h, l, c = d["high"], d["low"], d["close"]
    up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(h, c.shift(1)) - np.minimum(l, c.shift(1))
    w = lambda x: pd.Series(x).ewm(alpha=1 / 14, adjust=False).mean()
    atr_ = w(tr)
    pdi, ndi = 100 * w(pdm) / atr_, 100 * w(ndm) / atr_
    adx = w(100 * (pdi - ndi).abs() / (pdi + ndi))
    ema = c.ewm(span=50, adjust=False).mean()
    # known at the open of the next server day
    return pd.DataFrame({"side": np.sign(c - ema).shift(1).to_numpy(), "adx": adx.shift(1).to_numpy()},
                        index=d["day"])


def prepare(path: Path, frm: str, to: str) -> dict:
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["time"], unit="s")
    df = df[(df["ts"] >= pd.Timestamp(frm) - pd.Timedelta(days=10)) &
            (df["ts"] < pd.Timestamp(to) + pd.Timedelta(days=8))].reset_index(drop=True)
    bar_min = int(np.median(np.diff(df["time"].to_numpy())) // 60)
    ny = df["ts"] - pd.Timedelta(hours=7)
    st = d1_state()
    day = df["ts"].dt.normalize()
    c = df["close"]
    return dict(
        df=df, bar_min=bar_min, o=df["open"].to_numpy(), h=df["high"].to_numpy(), l=df["low"].to_numpy(),
        c=c.to_numpy(), sp=df["spread"].to_numpy() * 0.01, atr=atr(df).to_numpy(),
        ny_min=(ny.dt.hour * 60 + ny.dt.minute).to_numpy(), ny_date=ny.dt.normalize().to_numpy(),
        side=day.map(st["side"]).to_numpy(), adx=day.map(st["adx"]).to_numpy(),
        ema_m15=c.ewm(span=21 * 15 // bar_min, adjust=False).mean().to_numpy(),
        ema_h1=c.ewm(span=21 * 60 // bar_min, adjust=False).mean().to_numpy(),
        frm=pd.Timestamp(frm), to=pd.Timestamp(to))


def entries(P: dict, window: str, box: str, width: str, trend: str):
    """Yield (signal bar, direction, box high, box low) per NY date."""
    df, h, l, c, a = P["df"], P["h"], P["l"], P["c"], P["atr"]
    nm, nd = P["ny_min"], P["ny_date"]
    w0, w1 = (x * 60 for x in WINDOWS[window])
    starts = np.flatnonzero((nm == w0) & (df["ts"].to_numpy() >= P["frm"].to_datetime64()) &
                            (df["ts"].to_numpy() < P["to"].to_datetime64()))
    for s in starts:
        if box == "B60":
            b = np.arange(max(0, s - 60 // P["bar_min"]), s)
            b = b[nd[b] == nd[s]]
        else:   # ASIA: NY 19:00 of the prior NY date .. 03:00 of this one
            lo = s - (w0 - 3 * 60 + 8 * 60) // P["bar_min"] - 1
            b = np.arange(max(0, lo), s)
            m = ((nd[b] == nd[s]) & (nm[b] < 3 * 60)) | ((nd[b] < nd[s]) & (nm[b] >= 19 * 60))
            b = b[m & (P["df"]["ts"].to_numpy()[b] > P["df"]["ts"].to_numpy()[s] - np.timedelta64(20, "h"))]
        if len(b) < 3 or not a[s - 1] > 0:
            continue
        bh, bl = h[b].max(), l[b].min()
        if width == "W4" and bh - bl > (4 if box == "B60" else 12) * a[s - 1]:
            continue
        sd, adx = P["side"][s], P["adx"][s]
        allowed = {1, -1}
        if trend in ("TD", "TDA"):
            if not np.isfinite(sd) or sd == 0:
                continue
            allowed = {int(sd)}
            if trend == "TDA" and not adx >= 20:
                continue
        i = s
        while i < len(c) - 1 and nd[i] == nd[s] and nm[i] < w1:
            d = 1 if c[i] > bh else -1 if c[i] < bl else 0
            if d and d in allowed:
                yield i, d, bh, bl
                break
            i += 1


def simulate(P: dict, i: int, d: int, bh: float, bl: float, stop: str, exit_: str):
    o, h, l, c, sp, nm, nd = P["o"], P["h"], P["l"], P["c"], P["sp"], P["ny_min"], P["ny_date"]
    e = i + 1
    if e >= len(c):
        return None
    entry = o[e] + (sp[e] if d == 1 else 0.0)
    sl = (bl if d == 1 else bh) if stop == "SE" else (bh + bl) / 2
    risk = d * (entry - sl)
    if not risk > 0:
        return None
    tp = {"TP2": 2.0, "TP3": 3.0}.get(exit_)
    target = entry + d * tp * risk if tp else None
    end_day = nd[e]
    max_bars = 5 * 24 * 60 // P["bar_min"]
    ema = P["ema_h1"] if exit_ == "SW" else P["ema_m15"]
    j = e
    while True:
        lo, hi = l[j], h[j]
        if (d == 1 and lo <= sl) or (d == -1 and hi + sp[j] >= sl):
            px = sl
            break
        if target is not None and ((d == 1 and hi >= target) or (d == -1 and lo + sp[j] <= target)):
            px = target
            break
        intraday_end = exit_ != "SW" and (nd[j] != end_day or nm[j] >= 16 * 60 - P["bar_min"])
        trail = exit_ in ("EOD", "SW") and j > e and d * (c[j] - ema[j]) < 0
        if intraday_end or trail or j - e >= max_bars or j >= len(c) - 1:
            px = c[j] + (sp[j] if d == -1 else 0.0)
            break
        j += 1
    return dict(t=P["df"]["ts"].iat[i], d=d, r=d * (px - entry) / risk, risk_atr=risk / P["atr"][i],
                bars=j - e + 1)


def run(P: dict, label: str) -> pd.DataFrame:
    rows = []
    for window, box, width, trend in itertools.product(WINDOWS, ("B60", "ASIA"), ("W4", "WANY"), ("T0", "TD", "TDA")):
        sig = list(entries(P, window, box, width, trend))
        for stop, exit_ in itertools.product(("SE", "SM"), ("TP2", "TP3", "EOD", "SW")):
            for i, d, bh, bl in sig:
                r = simulate(P, i, d, bh, bl, stop, exit_)
                if r:
                    r.update(cell=f"{window}-{box}-{width}-{trend}-{stop}-{exit_}", period=label)
                    rows.append(r)
    return pd.DataFrame(rows)


def summary(t: pd.DataFrame) -> pd.DataFrame:
    def dd(x):
        eq = np.cumsum(x)
        return float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    g = t.sort_values("t").groupby("cell")
    s = g["r"].agg(n="size", mean_r="mean", win=lambda x: (x > 0).mean(), total_r="sum")
    s["max_dd_r"] = g["r"].apply(lambda x: dd(x.to_numpy()))
    yrs = (t["t"].max() - t["t"].min()).days / 365.25
    s["r_per_year"] = s["total_r"] / max(yrs, 0.1)
    return s


def control(P: dict, t_cell: pd.DataFrame, cell: str, reps: int = 300, seed: int = 7) -> float:
    """p-value: the cell's mean R vs entries at a random bar of the same window (same direction rule, box, exits)."""
    window, box, width, trend, stop, exit_ = cell.split("-")
    rng = np.random.default_rng(seed)
    sig = list(entries(P, window, box, width, trend))
    if not sig:
        return np.nan
    w0, w1 = (x * 60 for x in WINDOWS[window])
    means = []
    for _ in range(reps):
        rs = []
        for i, d, bh, bl in sig:
            s = i - (P["ny_min"][i] - w0) // P["bar_min"]
            k = s + rng.integers(0, (w1 - w0) // P["bar_min"])
            dd = d if trend != "T0" else rng.choice((-1, 1))
            r = simulate(P, k, dd, bh, bl, stop, exit_)
            if r:
                rs.append(r["r"])
        means.append(np.mean(rs) if rs else 0.0)
    return float((np.array(means) >= t_cell["r"].mean()).mean())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m5 = DATA / "m5v" / "XAUUSD.csv"
    res = {}
    for label, (a, b), path in (("disc", DISC, m5), ("test", TEST, m5), ("exam", EXAM, m5),
                                ("quiet_m15", QUIET, DATA / "m15v" / "XAUUSD.csv")):
        P = prepare(path, a, b)
        res[label] = (P, run(P, label))
        res[label][1].to_csv(OUT / f"xvb_{label}.csv", index=False)
    S = {k: summary(v[1]) for k, v in res.items()}
    tab = S["disc"][["n", "mean_r", "win", "r_per_year", "max_dd_r"]].add_prefix("D_").join(
        S["test"][["n", "mean_r", "r_per_year", "max_dd_r"]].add_prefix("T_")).join(
        S["quiet_m15"][["n", "mean_r"]].add_prefix("Q_")).join(S["exam"][["n", "mean_r"]].add_prefix("E_"))
    tab = tab.sort_values("D_r_per_year", ascending=False)
    tab.to_csv(OUT / "xvb_cells.csv")
    pd.set_option("display.width", 250)
    print("cells ranked by discovery R/year (selection uses discovery only)")
    print(tab.round(3).head(30).to_string())
    print("\ncells positive: disc", int((tab["D_mean_r"] > 0).sum()), "test", int((tab["T_mean_r"] > 0).sum()),
          "both", int(((tab["D_mean_r"] > 0) & (tab["T_mean_r"] > 0)).sum()), "of", len(tab))
    # pre-registered selection: best discovery R/year with >= 60 discovery trades
    pick = tab[tab["D_n"] >= 60].index[0]
    print("\nselected on discovery:", pick)
    p = control(res["test"][0], res["test"][1].query("cell == @pick"), pick)
    w, bx, wd, tr, st, ex = pick.split("-")
    neigh = [c for c in tab.index if sum(x != y for x, y in zip(c.split("-"), pick.split("-"))) == 1]
    share = float((tab.loc[neigh, "T_mean_r"] > 0).mean()) if neigh else np.nan
    row = tab.loc[pick]
    print(f"test n {row.T_n:.0f} mean {row.T_mean_r:+.3f}R  random-entry p {p:.3f}  neighbours positive on test "
          f"{share:.0%} ({len(neigh)})  quiet M15 {row.Q_mean_r:+.3f}R")
    ok = (row.T_n >= 60, row.T_mean_r > 0, p < 0.10, share >= 0.70, row.Q_mean_r >= -0.05)
    print("criteria (n>=60, test>0, p<0.10, neighbours>=70%, quiet>=-0.05):", ok, "PASS" if all(ok) else "FAIL")
    for lab in ("disc", "test", "exam"):
        t = res[lab][1].query("cell == @pick")
        if len(t):
            print(lab, "by direction:", t.groupby("d")["r"].agg(["size", "mean"]).round(3).to_dict("index"))


if __name__ == "__main__":
    main()
