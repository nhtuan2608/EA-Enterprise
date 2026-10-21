"""G140: sealed 01/2010-12/2017 holdout for two frozen candidates (plan docs/superpowers/plans/2026-10-22-g140-holdout-2010-2017.md).

  V  V-candle M30 candidate A (G118): fan against + ADX < 25 + EMA200 slope against, G116 hedge, stops +-2 ATR (A2), in U
  S  S07 G67 on H1 (comp 4, cooldown 2, hold 120, B6, E2X + TP 8) with the D1 state only, both directions

Usage: g140_holdout.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402
import g116_v_hedge as g116  # noqa: E402
import g118_v_combos as g118  # noqa: E402
from g117_v_filters import Sim2  # noqa: E402
from g134_extensions import prep_v  # noqa: E402

H0, HMID, H1_ = pd.Timestamp("2010-01-01"), pd.Timestamp("2014-01-01"), pd.Timestamp("2018-01-01")
RUNS, PVAL = 200, 0.025
random.seed(140)


def half_of(ts):
    if H0 <= ts < HMID:
        return "2010–2013"
    if HMID <= ts < H1_:
        return "2014–2017"
    if pd.Timestamp("2018-01-01") <= ts < pd.Timestamp("2026-07-01"):
        return "2018–06/2026 (đã biết)"
    return None


def stat(xs):
    xs = [x for x in xs if x == x]
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


# ------------------------------------------------------------------------------------------------ V
def touched(m, k):
    hi, lo, e = m["high"].to_numpy(), m["low"].to_numpy(), m["e200"].to_numpy()
    return any(lo[i] <= e[i] <= hi[i] for i in range(k - 3, k))


def ctx_a(m, k, s):
    e21, e55, e100, e200, a, adx = (m[c].to_numpy() for c in ("e21", "e55", "e100", "e200", "atr", "adx"))
    fan = 1 if e21[k] > e55[k] > e100[k] else (-1 if e21[k] < e55[k] < e100[k] else 0)
    slope = (e200[k] - e200[k - 48]) / a[k]
    return fan == -s and adx[k] < 25 and np.sign(slope) == -s


def part_v(root):
    m = prep_v(pd.read_csv(root / "m30v" / "XAUUSD.csv"))
    sp_raw = m["spread"].to_numpy() * 0.01
    med = float(np.median(sp_raw[sp_raw > 0]))
    gr = g116.find_groups(m)
    F = g118.features(m, gr)
    keep = (F["fan_against"] & F["adx_lt25"] & F["slope_against"]).to_numpy()
    V = [dict(v=v, j=j, s=int(F["vdir"].iat[q]), ts=m["ts"].iat[j]) for q, (v, j) in enumerate(gr) if keep[q]]
    for x in V:
        x["half"] = half_of(x["ts"]); x["year"] = x["ts"].year
    out = {}
    for mult, tag in ((1.0, "u"), (1.5, "u15")):
        m["sp"] = np.maximum(sp_raw, med) * mult
        S = Sim2(m)
        for x in V:
            x[tag] = S.hedge_r(x["v"], x["j"], "A2")[0]
    m["sp"] = np.maximum(sp_raw, med)
    S = Sim2(m)
    hold = [x for x in V if x["half"] in ("2010–2013", "2014–2017") and x["u"] == x["u"]]
    # random control: bars with context A and an EMA200 touch, same year and side
    pool = {}
    for k in range(300, len(m) - 8):
        ts = m["ts"].iat[k]
        if not (H0 <= ts < H1_) or not touched(m, k):
            continue
        for s in (1, -1):
            if ctx_a(m, k, s):
                pool.setdefault((ts.year, s), []).append(k)
    actual = float(np.mean([x["u"] for x in hold]))
    hits = 0
    for _ in range(RUNS):
        u = []
        for x in hold:
            cands = pool.get((x["year"], x["s"]), [])
            for _ in range(20):
                if not cands:
                    break
                k = random.choice(cands)
                r = S.hedge_r(k, k, "A2")[0]
                if r == r:
                    u.append(r); break
        hits += float(np.mean(u)) >= actual
    p = (hits + 1) / (RUNS + 1)
    for hf in ("2010–2013", "2014–2017", "2018–06/2026 (đã biết)"):
        out[hf] = stat(x["u"] for x in V if x["half"] == hf)
        out[hf + " phí×1,5"] = stat(x["u15"] for x in V if x["half"] == hf)
    out["2010–2017"] = stat(x["u"] for x in hold)
    out["2010–2017 phí×1,5"] = stat(x["u15"] for x in hold)
    out["theo năm"] = {str(y): stat(x["u"] for x in V if x["year"] == y) for y in range(2010, 2027)}
    out["mua / bán 2010–2017"] = [stat(x["u"] for x in hold if x["s"] == 1), stat(x["u"] for x in hold if x["s"] == -1)]
    out["p ngẫu nhiên 2010–2017"] = p
    h1, h2 = out["2010–2013"], out["2014–2017"]
    ok = (out["2010–2017"]["n"] >= 60 and h1.get("mean", -1) > 0 and h2.get("mean", -1) > 0
          and out["2010–2017 phí×1,5"]["mean"] > 0 and p <= PVAL)
    out["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return out


# ------------------------------------------------------------------------------------------------ S
def d1_merged(t, c):
    """State per bar: SMA50/200 of server-day closes, Sunday merged into Monday, last CLOSED day before the bar's day."""
    day = t // 86400
    key = day + ((day + 3) % 7 == 6)
    ends = np.r_[np.nonzero(np.diff(key))[0], len(key) - 1]
    lc, ks = c[ends], key[ends]
    s50 = np.convolve(lc, np.ones(50) / 50, "full")[:len(lc)]
    s200 = np.convolve(lc, np.ones(200) / 200, "full")[:len(lc)]
    st = np.where(np.arange(len(lc)) >= 199, np.sign(s50 - s200), 0)
    q = np.searchsorted(ks, key, side="left") - 1
    return np.where(q >= 0, st[np.maximum(q, 0)], 0).astype(int), key


def part_s(root):
    g.set_tf("H1")
    g.DATA = root / "h1v"
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = 4, 2, 120
    D = g.load("XAUUSD")
    st, _ = d1_merged(D["t"], D["c"])
    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    rows = []
    for t in g.trades("XAUUSD", "E2X", 8.0, None, sig):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        t["rh"] = h.harsh(t, D)
        t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
        t["st"] = int(st[t["i"]])
        t["ts"] = pd.Timestamp(int(D["t"][t["e0"]]), unit="s")
        t["half"] = half_of(t["ts"])
        rows.append(t)
    S = [t for t in rows if t["st"] == t["d"]]
    hold = [t for t in S if t["half"] in ("2010–2013", "2014–2017")]
    # random control: same direction, server hour, half, D1 state (= direction), exit and costs
    pool = {}
    n = len(D["t"])
    for j in range(250, n - 2):
        ts = pd.Timestamp(int(D["t"][j]), unit="s")
        hf = half_of(ts)
        if hf in ("2010–2013", "2014–2017") and st[j] != 0:
            pool.setdefault((hf, int(st[j]), int(D["t"][j] % 86400 // 3600)), []).append(j)
    actual = float(np.mean([t["rh"] for t in hold]))
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in hold:
            cands = pool.get((t["half"], t["d"], int(D["t"][t["i"]] % 86400 // 3600)), [])
            for _ in range(50):
                if not cands:
                    break
                r = g.walk(D, random.choice(cands), t["d"], "E2X", 8.0, None)
                if r is not None:
                    r["srv_in"], r["srv_out"] = int(D["t"][r["e0"]]), int(D["t"][r["x"]])
                    u.append(h.harsh(r, D)); break
        hits += float(np.mean(u)) >= actual
    p = (hits + 1) / (RUNS + 1)
    out = {}
    for hf in ("2010–2013", "2014–2017", "2018–06/2026 (đã biết)"):
        out[hf] = stat(t["rh"] for t in S if t["half"] == hf)
        out[hf + " mua / bán"] = [stat(t["rh"] for t in S if t["half"] == hf and t["d"] == 1),
                                  stat(t["rh"] for t in S if t["half"] == hf and t["d"] == -1)]
        out[hf + " ngược D1 (tham khảo)"] = stat(t["rh"] for t in rows if t["half"] == hf and t["st"] == -t["d"])
    out["2010–2017"] = stat(t["rh"] for t in hold)
    out["2010–2017 phí×1,5"] = stat(t["rh15"] for t in hold)
    out["theo năm"] = {str(y): stat(t["rh"] for t in S if t["ts"].year == y) for y in range(2010, 2027)}
    out["p ngẫu nhiên 2010–2017"] = p
    ok = (out["2010–2017"]["n"] >= 60 and out["2010–2013"].get("mean", -1) > 0 and out["2014–2017"].get("mean", -1) > 0
          and out["2010–2017 phí×1,5"]["mean"] > 0 and p <= PVAL)
    out["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    out["_trades"] = [dict(d=t["d"], ein=int(t["utc"]), eout=int(D["utc"][t["x"]]), r=t["rh"], half=t["half"]) for t in S]
    return out


def overlap_and_portfolio(root, s_trades):
    """Report only: overlap with the S07 M30 book (G89, built from 2010) and MAR of M30 + S at 0.5% per half."""
    import g89_full_book as fb
    from g134_extensions import sim
    fb.START = g.ts(2010, 1, 1)
    g.set_tf("M30")
    g.DATA = root / "m30v"
    P = g.load("XAUUSD")
    st, _ = d1_merged(P["t"], P["c"])
    legs = []
    for d in (1, -1):
        bases = []
        for main_, sub, t0, t1 in (("M30", "M30", fb.START, fb.SPLIT), ("M30", "M15", fb.SPLIT, fb.END)):
            bases += fb.base_book(fb.e73.context(main_, sub), d, t0, t1, early=True, re=True)
        for cl in fb.attach_adds(bases, fb.add_pool(d)):
            for j, L in enumerate(cl):
                k = int(np.searchsorted(P["t"], int(L["srv_in"]), side="right")) - 1
                w = ((1.0 if L.get("ord") else fb.W_UNORD) if j == 0 else fb.W_ADD) * (1.0 if st[k] == d else 0.5)
                legs.append(dict(d=d, ein=int(L["ein"]), eout=int(L["eout"]), r=float(L["rh"]), w=w))
    out = {}
    hold = [t for t in s_trades if t["half"] in ("2010–2013", "2014–2017")]
    ov = [any(x["d"] == t["d"] and x["ein"] <= t["ein"] < x["eout"] for x in legs) for t in hold]
    out["S trùng chân S07 M30 cùng chiều (2010–2017)"] = round(float(np.mean(ov)), 3) if ov else None
    out["S không trùng 2010–2017"] = stat(t["r"] for t, o in zip(hold, ov) if not o)
    m30 = [dict(t_in=x["ein"], t_out=x["eout"], r=x["r"], risk=0.015 * x["w"]) for x in legs]
    both = m30 + [dict(t_in=t["ein"], t_out=t["eout"], r=t["r"], risk=0.005) for t in s_trades]
    for name, a, z in (("2010–2013", g.ts(2010, 1, 1), g.ts(2014, 1, 1)), ("2014–2017", g.ts(2014, 1, 1), g.ts(2018, 1, 1))):
        out[f"M30 một mình {name}"] = [round(v, 4) if isinstance(v, float) else v for v in sim(m30, a, z)]
        out[f"M30 + S 0,5% {name}"] = [round(v, 4) if isinstance(v, float) else v for v in sim(both, a, z)]
        out[f"S07 M30 chân {name}"] = stat(x["r"] for x in legs if a <= x["ein"] < z)
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    res = {"V nến V M30 ứng viên A": part_v(root)}
    print("V", json.dumps(res["V nến V M30 ứng viên A"], ensure_ascii=False), flush=True)
    s = part_s(root)
    trades = s.pop("_trades")
    res["S S07 H1 cùng D1"] = s
    print("S", json.dumps(s, ensure_ascii=False), flush=True)
    res["S báo thêm"] = overlap_and_portfolio(root, trades)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res["S báo thêm"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
