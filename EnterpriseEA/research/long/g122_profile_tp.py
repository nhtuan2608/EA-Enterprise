"""G122: multi-day volume profile levels as take-profit for S07 and VHedge (plan docs/superpowers/plans/2026-10-15-g122-profile-tp.md).

  python g122_profile_tp.py            -> train / validate with fake-level controls (test periods sealed)

Profiles: M30 tick volume spread evenly over each bar's low..high, bins of ATR14(D1)/20, smoothed over 3 bins, over the
5 (P5) or 20 (P20) closed server days before the entry day. Levels: POC, VAH/VAL (70%), HVN (local peaks >= 0.6 POC).
Target: the nearest level of the set in the trade direction at least minR x R beyond the entry (fixed at the entry).
FULL: everything closes at the target if it trades before the original exit; HALF: 50% there, the rest as before.
Fake levels: all levels of the trade shifted by one random offset of +-(0.5..2) x VA width, 200 times.
"""
from __future__ import annotations

import itertools
import time

import numpy as np
import pandas as pd

from g97_forming_bar import dmi

HERE = __import__("pathlib").Path(__file__).resolve().parent
SCR = HERE / "out"
REPS = 200
TP_COST = 0.40
PER = {
    "S07": {"train": ("2018-03-01", "2023-01-01"), "validate": ("2023-01-01", "2025-01-01")},
    "VH": {"train": ("2024-05-14", "2025-07-01"), "validate": ("2025-07-01", "2026-01-01")},
}
WINS = (5, 20)
SETS = ("HVN", "VA")
MINR = {"S07": (1.0, 2.0, 3.0), "VH": (2.0, 3.0, 5.0)}
MODES = ("FULL", "HALF")


# --------------------------------------------------------------------------------------------- profiles
class Profiles:
    def __init__(self):
        b = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
        b["day"] = b["time"] // 86400
        self.days = np.sort(b["day"].unique())
        self.by_day = {d: (g["low"].to_numpy(), g["high"].to_numpy(), g["tickvol"].to_numpy().astype(float))
                       for d, g in b.groupby("day")}
        D = b.groupby("day").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
        _, _, _, atr = dmi(D["high"].to_numpy(), D["low"].to_numpy(), D["close"].to_numpy())
        self.atr_d1 = dict(zip(D.index.to_numpy(), atr))
        self.cache = {}

    @staticmethod
    def hist(lo, hi, vol, w, base):
        a = np.floor((lo - base) / w).astype(int)
        z = np.floor((hi - base) / w).astype(int)
        n = int(z.max()) + 2
        diff = np.zeros(n + 1)
        per = vol / (z - a + 1)
        np.add.at(diff, a, per)
        np.add.at(diff, z + 1, -per)
        return np.cumsum(diff)[:n]

    def levels(self, day, win):
        """Levels from the `win` closed server days before `day` (epoch day number)."""
        key = (day, win)
        if key in self.cache:
            return self.cache[key]
        k = int(np.searchsorted(self.days, day))
        if k < win + 15:
            self.cache[key] = None
            return None
        prev = self.days[k - win:k]
        atr = self.atr_d1.get(self.days[k - 1], np.nan)
        if not np.isfinite(atr) or atr <= 0:
            self.cache[key] = None
            return None
        lo = np.concatenate([self.by_day[d][0] for d in prev])
        hi = np.concatenate([self.by_day[d][1] for d in prev])
        vol = np.concatenate([self.by_day[d][2] for d in prev])
        w = atr / 20
        base = lo.min()
        c = self.hist(lo, hi, vol, w, base)
        c = np.convolve(c, np.ones(3) / 3, mode="same")
        poc = int(np.argmax(c))
        tot, va, a, z = c.sum(), c[poc], poc, poc
        while va < 0.7 * tot:
            left = c[a - 1] if a > 0 else -1
            right = c[z + 1] if z < len(c) - 1 else -1
            if right >= left:
                z += 1; va += c[z]
            else:
                a -= 1; va += c[a]
        px = lambda i: base + (i + 0.5) * w
        hvn = [px(i) for i in range(1, len(c) - 1) if c[i] >= 0.6 * c[poc] and c[i] >= c[i - 1] and c[i] >= c[i + 1]]
        L = dict(poc=px(poc), vah=base + (z + 1) * w, val=base + a * w, hvn=np.array(sorted(set(hvn + [px(poc)]))))
        L["HVN"] = L["hvn"]
        L["VA"] = np.array(sorted((L["val"], L["poc"], L["vah"])))
        L["width"] = L["vah"] - L["val"]
        self.cache[key] = L
        return L


def target(levels, d, entry, risk, minr, off=0.0):
    x = levels + off
    dist = d * (x - entry)
    ok = dist >= minr * risk
    if not ok.any():
        return None
    return float(x[ok][np.argmin(dist[ok])])


def tick_check(P):
    """Correlation of the M30 even-spread profile with the G121 tick profile for single days (2024+)."""
    import glob
    out = []
    for f in sorted(glob.glob(str(HERE / "data" / "ticks" / "profile_*.npz")))[::3]:
        z = np.load(f, allow_pickle=True)
        for day, lo, cnt in zip(z["days"], z["lo"], z["counts"]):
            d = int(day) // 86400
            if d not in P.by_day:
                continue
            l, h, v = P.by_day[d]
            base = min(float(lo), float(l.min()))
            m = Profiles.hist(l, h, v, 0.5, base)
            k0 = int(round((float(lo) - base) / 0.5))
            tk = np.zeros(max(len(m), k0 + len(cnt)))
            tk[k0:k0 + len(cnt)] = cnt
            mm = np.zeros(len(tk)); mm[:len(m)] = m
            if len(cnt) > 20:
                out.append((np.corrcoef(mm, tk)[0, 1], abs(np.argmax(mm) - np.argmax(tk)) * 0.5))
    a = np.array(out)
    return len(a), np.nanmean(a[:, 0]), np.nanmedian(a[:, 1])


# --------------------------------------------------------------------------------------------- S07
def s07_book(P):
    import g107_portfolio as p
    L = pd.DataFrame(p.s07_legs())
    L = L[(L.t_in >= "2018-03-01") & (L.t_in < "2025-01-01")].reset_index(drop=True)   # 2025+ sealed
    b = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
    t = pd.to_datetime(b["time"], unit="s").to_numpy()
    h, l, sp = b["high"].to_numpy(), b["low"].to_numpy(), b["spread"].to_numpy() * 0.01
    hmax, lmin, lv = [], [], {}
    for r in L.itertuples():
        a = int(np.searchsorted(t, np.datetime64(r.t_in)))
        z = int(np.searchsorted(t, np.datetime64(r.t_out)))
        hmax.append(h[a:z].max() if z > a else -np.inf)
        lmin.append((l[a:z] + sp[a:z]).min() if z > a else np.inf)
    L["hmax"], L["lmin"] = hmax, lmin
    L["day"] = ((L["t_in"] - pd.Timestamp(0)).dt.total_seconds() // 86400).astype(int)
    return L


def s07_eval(L, P, win, st, minr, rng=None, idx=None):
    out = L["r"].to_numpy().copy()
    rows = list(L.itertuples())
    for i in (range(len(L)) if idx is None else idx):
        r = rows[i]
        lv = P.levels(r.day, win)
        if lv is None:
            continue
        off = 0.0 if rng is None else rng.choice((-1, 1)) * rng.uniform(0.5, 2) * lv["width"]
        T = target(lv[st], r.d, r.entry, r.risk, minr, off)
        if T is None:
            continue
        hit = (r.hmax >= T) if r.d == 1 else (r.lmin <= T)
        if hit:
            out[i] = r.d * (T - r.entry) / r.risk - TP_COST / r.risk
    return out


# --------------------------------------------------------------------------------------------- VHedge
def vh_book():
    import g116_v_hedge as g
    import g118_v_combos as g118
    import g119_v_m5_native as q
    import g120_vhedge_v2 as v2

    class SimT(v2.SimV2):
        tgt = None

        def manage(self, t, d, legs, surv_entry, surv_sl, mode, k):
            R = d * (surv_entry - surv_sl)
            if self.tgt is not None and R > 0:
                T = self.tgt(t, d, surv_entry, R)
                if T is not None:
                    k = d * (T - surv_entry) / R
            return super().manage(t, d, legs, surv_entry, surv_sl, mode, k)

    m = g118.load("M5")
    gr = g.find_groups(m)
    F = q.raw_features(m, gr)
    BF = q.binarize(F, F[F.t < "2025-01-01"])
    PF = v2.profiles(BF, v2.m30_context(m, F))
    S = SimT(m)
    S.days = (m["time"].to_numpy() // 86400)
    keep = (F.t < "2026-01-01").to_numpy()                                 # 2026 sealed
    books = {}
    for prof, mult in (("G119", 1.5), ("BIGV", 1.0)):
        sel = np.flatnonzero(PF[prof] & keep)
        books[prof] = dict(groups=[gr[i] for i in sel], t=F.t.to_numpy()[sel], mult=mult)
    return S, books


def r2d(S, v, j, mult):
    """G120 r2 that also returns the survivor direction (0 = both legs closed together / none)."""
    mid = S.o[j + 1]
    S.h[v], S.l[v] = mid + mult * S.atr[j], mid - mult * S.atr[j]
    res = S.hedge(v, j, 0.1, 3, "K", "SAME", "E0", 5.0)
    S._reset(v)
    return (np.nan, 0) if res is None else (res[0], res[1])


def vh_eval(S, bk, P, win, st, minr, rng=None, idx=None):
    def tgt(t, d, entry, R):
        lv = P.levels(int(S.days[t]), win)
        if lv is None:
            return None
        off = 0.0 if rng is None else rng.choice((-1, 1)) * rng.uniform(0.5, 2) * lv["width"]
        return target(lv[st], d, entry, R, minr, off)
    S.tgt = tgt
    out = bk["base"].copy()
    for i in (range(len(out)) if idx is None else idx):
        v, j = bk["groups"][i]
        out[i] = r2d(S, v, j, bk["mult"])[0]
    S.tgt = None
    return out


# --------------------------------------------------------------------------------------------- study
def cell_rows(bot, t, d, base, full, fakes_full, per, name):
    """full / fakes_full: FULL-mode R per trade; HALF derived as 0.5 x FULL + 0.5 x base (legs are independent)."""
    rows = []
    for mode in MODES:
        f = (lambda x: x) if mode == "FULL" else (lambda x: 0.5 * x + 0.5 * base)
        real = f(full)
        for p, (a, b) in per.items():
            mk = (t >= np.datetime64(a)) & (t < np.datetime64(b)) & ~np.isnan(real) & ~np.isnan(base)
            if mk.sum() == 0:
                continue
            dl = real[mk] - base[mk]
            row = dict(bot=bot, cell=f"{name} {mode}", period=p, n=int(mk.sum()), base_R=base[mk].mean(),
                       new_R=real[mk].mean(), dR=dl.mean(), dR_buy=dl[d[mk] == 1].mean() if (d[mk] == 1).any() else np.nan,
                       dR_sell=dl[d[mk] == -1].mean() if (d[mk] == -1).any() else np.nan,
                       changed=float((np.abs(dl) > 1e-9).mean()))
            if p == "validate":
                fk = np.array([np.nanmean(f(x)[mk] - base[mk]) for x in fakes_full])
                row["fake_dR"] = np.nanmedian(fk)
                row["p"] = float(np.mean(fk >= dl.mean()))
            rows.append(row)
    return rows


def main():
    t0 = time.time()
    P = Profiles()
    n, corr, poc = tick_check(P)
    print(f"profile check vs ticks: {n} days, corr {corr:.3f}, median POC gap ${poc:.2f}", flush=True)
    rng = np.random.default_rng(122)
    rows = []

    L = s07_book(P)
    print(f"S07 legs {len(L)} ({time.time() - t0:.0f}s)", flush=True)
    tS, dS, baseS = L["t_in"].to_numpy(), L["d"].to_numpy(), L["r"].to_numpy()
    va, vb = PER["S07"]["validate"]
    vidx = np.flatnonzero((tS >= np.datetime64(va)) & (tS < np.datetime64(vb)))
    for win, st, minr in itertools.product(WINS, SETS, MINR["S07"]):
        name = f"P{win} {st} {minr:g}R"
        full = s07_eval(L, P, win, st, minr)
        fakes = [s07_eval(L, P, win, st, minr, rng, vidx) for _ in range(REPS)]
        rows += cell_rows("S07", tS, dS, baseS, full, fakes, PER["S07"], name)
        print("S07", name, f"({time.time() - t0:.0f}s)", flush=True)

    S, books = vh_book()
    va, vb = PER["VH"]["validate"]
    for prof, bk in books.items():
        rd = [r2d(S, v, j, bk["mult"]) for v, j in bk["groups"]]
        bk["base"] = np.array([x[0] for x in rd])
        dV = np.array([x[1] for x in rd])
        vidx = np.flatnonzero((bk["t"] >= np.datetime64(va)) & (bk["t"] < np.datetime64(vb)))
        print(f"VH {prof} groups {len(bk['groups'])}, validate {len(vidx)}", flush=True)
        for win, st, minr in itertools.product(WINS, SETS, MINR["VH"]):
            name = f"P{win} {st} {minr:g}R"
            full = vh_eval(S, bk, P, win, st, minr)
            fakes = [vh_eval(S, bk, P, win, st, minr, rng, vidx) for _ in range(REPS)]
            rows += cell_rows(f"VH-{prof}", bk["t"], dV, bk["base"], full, fakes, PER["VH"], name)
            print("VH", prof, name, f"({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(SCR / "g122_profile_tp.csv", index=False)
    W = T.pivot_table(index=["bot", "cell"], columns="period",
                      values=["n", "base_R", "dR", "dR_buy", "dR_sell", "fake_dR", "p"], aggfunc="first")
    W.columns = [f"{b[:3]}_{a}" for a, b in W.columns]
    pd.set_option("display.width", 260)
    pd.set_option("display.max_rows", 200)
    print(W.round(3).to_string())


if __name__ == "__main__":
    main()
