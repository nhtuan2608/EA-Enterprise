import csv, glob, sys
from collections import Counter
from datetime import datetime, timezone
sys.path.insert(0, r"D:\Work\Private\Trading\EA-Enterprise\.worktrees\g67-dmi-ema\EnterpriseEA\research\long")
import numpy as np
import g67_dmi_ema as g
import g76_dxy as g76
import g77_dxy_tf as m

def yr(t): return datetime.fromtimestamp(int(t), timezone.utc).year
out = []
P = lambda *a: out.append(" ".join(str(x) for x in a))

# 1. DXY data integrity
for tf in ("M15", "M30"):
    rows = list(csv.DictReader(open(g.HERE / "data" / f"{tf.lower()}v" / "DXY.csv")))
    t = np.array([int(r["time"]) for r in rows])
    step = m.SEC[tf]
    d = np.diff(t)
    P(f"[1] DXY {tf}: {len(t)} bars, duplicates {int(np.sum(d == 0))}, unsorted {int(np.sum(d < 0))}, "
      f"gaps >1 bar inside weekday {int(np.sum((d > step) & (d < 6 * 3600)))}, gaps >6h {int(np.sum(d >= 6 * 3600))}")
    per_year = Counter(yr(x) for x in t)
    P("    bars per year:", dict(sorted(per_year.items())))
    hours = Counter(int((x % 86400) // 3600) for x in t)
    P("    server hours present:", sorted(hours))
    # raw vs terminal overlap check
    f = sorted(glob.glob(str(g76.RAW / f"USDX._{tf}_*.csv")))[-1]
    raw_last = None
    with open(f) as fh:
        rd = csv.reader(fh, delimiter="\t"); next(rd)
        for r in rd: raw_last = r
    P(f"    raw file ends {raw_last[0]} {raw_last[1]} close {raw_last[5]}")

# gold server hours for comparison
rows = list(csv.DictReader(open(g.HERE / "data" / "m30v" / "XAUUSD.csv")))
gt = np.array([int(r["time"]) for r in rows])
P("[1] XAU M30 server hours present:", sorted(Counter(int((x % 86400) // 3600) for x in gt[gt >= g76.START])))

# 2. correlation and lag (M30 returns, matched server times)
m.configure("M30"); X = g.load("DXY"); xt, xc = X["t"].copy(), X["c"].copy()
m.configure("M30"); G = g.load("XAUUSD")
pos = {int(a): k for k, a in enumerate(xt)}
idx = [(i, pos[int(G["t"][i])]) for i in range(1, len(G["t"])) if int(G["t"][i]) in pos and int(G["t"][i - 1]) in pos and G["utc"][i] >= g76.START]
gi = np.array([a for a, _ in idx]); xi = np.array([b for _, b in idx])
gr = np.log(G["c"][gi] / G["c"][gi - 1])
for lag in (-2, -1, 0, 1, 2):
    xr = np.log(xc[xi + lag] / xc[xi + lag - 1]) if lag >= 0 else np.log(xc[xi + lag] / xc[xi + lag - 1])
    P(f"[2] corr(gold M30 return, DXY return lag {lag:+d} bar) = {np.corrcoef(gr, xr)[0, 1]:+.3f}")
for y in range(2021, 2027):
    k = np.array([yr(G["utc"][i]) == y for i in gi])
    xr = np.log(xc[xi] / xc[xi - 1])
    P(f"    {y}: corr {np.corrcoef(gr[k], xr[k])[0, 1]:+.3f} (n {int(k.sum())})")

# 3. look-ahead audit of T1 when DXY closes inside a gold bar
for gtf, xtf in m.COMBOS:
    Xd = m.dxy(xtf); Gd = m.gold(gtf)
    gclose = Gd["t"] + m.SEC[gtf]
    n_all = n_mid = 0
    for tc in Xd["sig_close"]:
        i = int(np.searchsorted(gclose, tc, side="right")) - 1
        if i < 400 or i >= len(Gd["t"]) - 1:
            continue
        n_all += 1
        n_mid += int(gclose[i] < tc)          # entry at o[i+1] = gclose[i] would be before the DXY signal closed
    P(f"[3] T1 gold {gtf} x DXY {xtf}: {n_mid}/{n_all} DXY signals close inside a gold bar (entry before the signal = look-ahead)")

# 3b. T1 gold M30 x DXY M15 with only aligned closes (no look-ahead)
Xd = m.dxy("M15"); Gd = m.gold("M30")
res = m.variants("M30", Xd, Gd)
gclose = Gd["t"] + 1800
ok_sig = set()
for tc, dx in zip(Xd["sig_close"], Xd["sig_dir"]):
    i = int(np.searchsorted(gclose, tc, side="right")) - 1
    if 400 <= i < len(Gd["t"]) - 1 and gclose[i] == tc and Gd["h4_side"][i] == -dx and Gd["utc"][i] >= g76.START:
        ok_sig.add((i, -int(dx)))
t1c = [m.finish(Gd, t) for t in g.trades("XAUUSD", "E2X", 8.0, None, sorted(ok_sig))]
for d, dn in ((1, "buy"), (-1, "sell")):
    s0, s1 = m.stats(res["T1"], d), m.stats(t1c, d)
    f = lambda s: " / ".join(f"{s['per'][q]['n']} {s['per'][q]['exp']:+.3f}" for q in m.DECIDE)
    P(f"[3b] T1 M30xM15 {dn}: as reported {f(s0)} | aligned closes only {f(s1)}")

# 4. significance: F1 M15xM15 buy removed trades; F3 label M30xM30 buy
rng = np.random.default_rng(1)
def perm(base, kept_ids, label):
    b = [t for t in base if t["d"] == 1 and t["p"] in m.DECIDE]
    r = np.array([t["rh"] for t in b])
    k = np.array([(t["i"]) in kept_ids for t in b])
    real = r[k].mean() - r.mean()
    sims = np.array([r[rng.permutation(len(r))[:k.sum()]].mean() - r.mean() for _ in range(5000)])
    rem = r[~k]
    P(f"[4] {label}: kept {k.sum()}/{len(r)}, kept mean {r[k].mean():+.3f}, removed mean {rem.mean():+.3f} (n {len(rem)}), "
      f"lift {real:+.3f}R, permutation p = {np.mean(sims >= real):.3f}")
    # by period
    for q in m.DECIDE:
        kk = np.array([t["p"] == q for t in b])
        P(f"      {q}: kept {r[k & kk].mean():+.3f} (n {int((k & kk).sum())}) removed {r[~k & kk].mean() if (~k & kk).any() else float('nan'):+.3f} (n {int((~k & kk).sum())})")

Xd = m.dxy("M15"); Gd = m.gold("M15"); res = m.variants("M15", Xd, Gd)
perm(res["B0"], {t["i"] for t in res["F1"]}, "F1 gold M15 x DXY M15 buy")
Xd = m.dxy("M30"); Gd = m.gold("M30"); res = m.variants("M30", Xd, Gd)
perm(res["B0"], {t["i"] for t in res["F3"]}, "F3 label gold M30 x DXY M30 buy")
# note: F3/F1 trade sets come from re-running g.trades on the filtered signals (cool-down can shift entries)
same = len({t["i"] for t in res["F3"]} & {t["i"] for t in res["B0"]})
P(f"[4] F3 trades that are also B0 trades: {same}/{len(res['F3'])}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
