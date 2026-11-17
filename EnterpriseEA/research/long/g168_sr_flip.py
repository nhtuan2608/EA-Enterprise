"""G168: limit orders at H1 S/R levels in the D1 direction (LFX-style ambush). Variant F = broken swing level (S/R flip),
variant R = nearest unbroken swing. Controls: fake levels (C1), market entry (C2), no D1 gate (C3).
Plan: docs/superpowers/plans/2026-11-17-g168-sr-flip-limit.md.

Usage: g168_sr_flip.py <research data dir> <g168 results dir (holds mt5_XAUUSD_*.csv)>
"""
import json
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

START, SPLIT, END = pd.Timestamp("2018-05-01").value // 10**9, pd.Timestamp("2023-01-01").value // 10**9, pd.Timestamp("2026-11-18").value // 10**9
COMM_OZ, SWAP_OZ = 0.06, 0.30
SEED, BOOT, RUNS = 168, 2000, 200
ALPHA = 0.05 / 2
LFX_FROM = pd.Timestamp("2026-11-04").value // 10**9


@dataclass(frozen=True)
class Cfg:
    variant: str = "F"
    sl_atr: float = 1.3
    off_atr: float = 0.2
    expiry_h: int = 24
    gate: bool = True
    market: bool = False
    cost_mult: float = 1.0
    swap_oz: float = SWAP_OZ


# ---------------------------------------------------------------------------------------------------- data
def load(root, res):
    def merge(a, b):
        a = pd.read_csv(a)
        b = pd.read_csv(b)
        b = b[b["time"] > a["time"].max()]
        b = b.rename(columns={"tick_volume": "tickvol"})
        d = pd.concat([a, b[[c for c in a.columns if c in b.columns]]], ignore_index=True)
        return d
    h1 = merge(Path(root) / "h1v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_H1.csv")
    m30 = merge(Path(root) / "m30v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_M30.csv")
    m5 = merge(Path(root) / "m5v" / "XAUUSD.csv", Path(res) / "mt5_XAUUSD_M5.csv")
    for d in (h1, m30, m5):
        d["sp"] = np.maximum(d["spread"].fillna(0).to_numpy() * 0.01, 0.10)
    return h1, m30, m5


def prep_h1(h1):
    t, o, h, l, c = (h1[k].to_numpy() for k in ("time", "open", "high", "low", "close"))
    n = len(c)
    pc = np.r_[c[0], c[:-1]]
    atr = pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    # D1 regime of the last closed server day (R1: close vs EMA50 and EMA50 10-day slope)
    day = t // 86400
    ends = np.r_[np.nonzero(np.diff(day))[0], n - 1]
    dc, dd = c[ends], day[ends]
    e50 = pd.Series(dc).ewm(span=50, adjust=False).mean().to_numpy()
    st = np.zeros(len(dc), int)
    for k in range(60, len(dc)):
        if dc[k] > e50[k] and e50[k] > e50[k - 10]:
            st[k] = 1
        elif dc[k] < e50[k] and e50[k] < e50[k - 10]:
            st[k] = -1
    q = np.searchsorted(dd, day, side="left") - 1
    reg = np.where(q >= 0, st[np.maximum(q, 0)], 0)
    # confirmed pivots 3/3: (confirm index, price)
    K = 3
    piv_h = [(i + K, h[i]) for i in range(K, n - K) if h[i] == h[i - K:i + K + 1].max()]
    piv_l = [(i + K, l[i]) for i in range(K, n - K) if l[i] == l[i - K:i + K + 1].min()]
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "atr": atr, "reg": reg, "ph": piv_h, "pl": piv_l, "n": n}


# ---------------------------------------------------------------------------------------------------- candidate orders
def candidates(H, cfg):
    """Placement events at H1 closes: (h1 index, side, limit price, atr, tp3 swing list for the side)."""
    t, c, atr, reg, n = H["t"], H["c"], H["atr"], H["reg"], H["n"]
    ph, pl = H["ph"], H["pl"]
    i0 = int(np.searchsorted(t, START - 20 * 86400))
    out = []
    used = set()
    jh = jl = 0
    act_h, act_l = [], []
    for i in range(max(i0, 300), n):
        while jh < len(ph) and ph[jh][0] <= i:
            act_h.append(ph[jh]); jh += 1
        while jl < len(pl) and pl[jl][0] <= i:
            act_l.append(pl[jl]); jl += 1
        if i % 50 == 0:
            act_h = [p for p in act_h if i - p[0] <= 240]
            act_l = [p for p in act_l if i - p[0] <= 240]
        a = atr[i]
        sides = [int(reg[i])] if cfg.gate else [1, -1]
        for d in sides:
            if d == 0:
                continue
            if cfg.variant == "F":
                # sell: a swing low broken by this close; buy: a swing high broken
                pool = act_l if d == -1 else act_h
                for ci, lv in pool:
                    key = ("F", d, ci)
                    if key in used:
                        continue
                    broke = (c[i] < lv - 0.3 * a and c[i - 1] >= lv - 0.3 * a) if d == -1 else (c[i] > lv + 0.3 * a and c[i - 1] <= lv + 0.3 * a)
                    if broke:
                        used.add(key)
                        price = lv - d * cfg.off_atr * a if d == -1 else lv + cfg.off_atr * a
                        price = lv - cfg.off_atr * a if d == -1 else lv + cfg.off_atr * a
                        if -d * (price - c[i]) >= 0.5 * a:
                            out.append((i, d, price, a, lv))
            else:
                pool = act_h if d == -1 else act_l
                best = None
                for ci, lv in pool:
                    price = lv - cfg.off_atr * a if d == -1 else lv + cfg.off_atr * a
                    dist = -d * (price - c[i])
                    if 0.5 * a <= dist <= 3 * a and ("R", d, ci) not in used:
                        if best is None or dist < best[0]:
                            best = (dist, ci, lv, price)
                if best:
                    out.append((i, d, best[3], a, best[2], ("R", d, best[1])))
    return out


# ---------------------------------------------------------------------------------------------------- execution
def run(H, X, cfg, events, rng=None):
    """events: (h1 idx, side, price, atr, level[, key]) ; X = execution bars. One pending + one open per side."""
    tx, ox, hx, lx, cx, spx = (X[k].to_numpy() for k in ("time", "open", "high", "low", "close", "sp"))
    med = float(np.median(spx[-50000:]))
    slip = 0.5 * med * cfg.cost_mult
    comm = COMM_OZ * cfg.cost_mult
    t1, c1 = H["t"], H["c"]
    trades = []
    busy_until = {1: -1, -1: -1}           # execution index until which the side is occupied
    used_keys = set()
    for ev in events:
        i, d, price, a, lv = ev[:5]
        key = ev[5] if len(ev) > 5 else None
        place_t = t1[i] + 3600                                            # close of the H1 bar
        if place_t < START or place_t >= END:
            continue
        k0 = int(np.searchsorted(tx, place_t))
        if k0 >= len(tx) or k0 <= busy_until[d]:
            continue
        if key is not None and key in used_keys:
            continue
        expiry = place_t + cfg.expiry_h * 3600
        fill_k, fill_px = None, None
        if cfg.market:
            fill_k = k0
            fill_px = ox[k0] + (spx[k0] + slip if d == 1 else -slip)
        else:
            for k in range(k0, len(tx)):
                if tx[k] >= expiry:
                    break
                if H["reg"][min(H["n"] - 1, int(np.searchsorted(t1, tx[k], side="right")) - 1)] != d and cfg.gate:
                    break                                                   # regime changed: cancel
                if d == -1 and hx[k] >= price:
                    fill_k, fill_px = k, max(price, ox[k]) - slip
                    break
                if d == 1 and lx[k] + spx[k] <= price:
                    fill_k, fill_px = k, min(price, ox[k] + spx[k]) + slip
                    break
        if fill_k is None:
            busy_until[d] = max(busy_until[d], int(np.searchsorted(tx, expiry)) - 1)
            if key is not None:
                used_keys.add(key)
            continue
        if key is not None:
            used_keys.add(key)
        risk = cfg.sl_atr * a
        sl = fill_px - d * risk
        tp = [fill_px + d * risk, fill_px + d * 2 * risk]
        # TP3: nearest confirmed opposite swing beyond 2R (swing lows for sells, highs for buys), else 3R
        pool = H["pl"] if d == -1 else H["ph"]
        cand = [p for ci, p in pool if ci <= i and i - ci <= 240 and d * (p - tp[1]) > 0]
        tp.append(min(cand, key=lambda p: abs(p - tp[1])) if cand else fill_px + d * 3 * risk)
        parts_open = [True, True, True]
        r_parts = [0.0, 0.0, 0.0]
        stop = sl
        k_end = fill_k
        exit_reason = None
        time_limit = tx[fill_k] + 72 * 3600
        for k in range(fill_k, len(tx)):
            adv = lx[k] if d == 1 else hx[k] + spx[k]
            fav = hx[k] if d == 1 else lx[k] + spx[k]
            if d * (adv - stop) <= 0:
                px = (min(stop, ox[k]) if d == 1 else max(stop, ox[k] + spx[k])) if k > fill_k else stop
                px -= d * slip
                for j in range(3):
                    if parts_open[j]:
                        r_parts[j] = d * (px - fill_px) / risk
                        parts_open[j] = False
                k_end, exit_reason = k, "SL" if stop == sl else "BE"
                break
            for j in range(3):
                if parts_open[j] and d * (fav - tp[j]) >= 0:
                    r_parts[j] = d * (tp[j] - d * slip - fill_px) / risk
                    parts_open[j] = False
                    if j == 0:
                        stop = fill_px
            if not any(parts_open):
                k_end, exit_reason = k, "TP3"
                break
            if tx[k] >= time_limit:
                px = cx[k] - d * slip - (spx[k] if d == -1 else 0)
                for j in range(3):
                    if parts_open[j]:
                        r_parts[j] = d * (px - fill_px) / risk
                        parts_open[j] = False
                k_end, exit_reason = k, "hết giờ"
                break
        else:
            continue
        nights = int(tx[k_end] // 86400 - tx[fill_k] // 86400)
        cost = (comm + nights * cfg.swap_oz) / risk
        R = float(np.mean(r_parts)) - cost
        trades.append({"place": int(place_t), "fill": int(tx[fill_k]), "exit": int(tx[k_end]), "d": d, "R": R, "reason": exit_reason,
                       "price": float(price), "level": float(lv), "atr": float(a), "wait_h": round((tx[fill_k] - place_t) / 3600, 1),
                       "hold_h": round((tx[k_end] - tx[fill_k]) / 3600, 1), "fill_px": float(fill_px), "sl": float(sl), "tp": [float(x) for x in tp]})
        busy_until[d] = k_end
    return trades


def stats(tr, a=START, z=END):
    x = [q for q in tr if a <= q["place"] < z]
    if not x:
        return {"n": 0, "tổng R": 0.0}
    r = np.array([q["R"] for q in sorted(x, key=lambda q: q["exit"])])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    pos, neg = r[r > 0].sum(), -r[r < 0].sum()
    weeks = (min(z, END) - a) / (7 * 86400)
    reasons = {}
    for q in x:
        reasons[q["reason"]] = reasons.get(q["reason"], 0) + 1
    return {"n": len(r), "lệnh / tuần": round(len(r) / weeks, 2), "tỷ lệ thắng": round(float(np.mean(r > 0)), 3), "R TB": round(float(r.mean()), 3),
            "tổng R": round(float(r.sum()), 1), "PF": round(float(pos / neg), 2) if neg > 0 else None, "DD R": round(dd, 1),
            "MAR": round(float(r.sum()) / dd, 2) if dd > 0 else None,
            "mua: n / R TB": [int(sum(1 for q in x if q["d"] == 1)), round(float(np.mean([q["R"] for q in x if q["d"] == 1])), 3) if any(q["d"] == 1 for q in x) else None],
            "bán: n / R TB": [int(sum(1 for q in x if q["d"] == -1)), round(float(np.mean([q["R"] for q in x if q["d"] == -1])), 3) if any(q["d"] == -1 for q in x) else None],
            "chờ khớp TB (h)": round(float(np.mean([q["wait_h"] for q in x])), 1), "giữ TB (h)": round(float(np.mean([q["hold_h"] for q in x])), 1),
            "lý do": reasons}


def boot_ci(tr, rng):
    x = [q for q in tr if START <= q["place"] < END]
    wk = {}
    for q in x:
        wk.setdefault(q["place"] // (7 * 86400), []).append(q["R"])
    W = [np.array(v) for v in wk.values()]
    sums = np.array([v.sum() for v in W]); cnts = np.array([len(v) for v in W])
    bs = []
    for _ in range(BOOT):
        idx = rng.integers(0, len(W), len(W))
        bs.append(sums[idx].sum() / cnts[idx].sum())
    return [round(float(np.percentile(bs, 100 * ALPHA / 2)), 3), round(float(np.percentile(bs, 100 * (1 - ALPHA / 2))), 3)]


def fake_events(H, events, rng):
    swings = np.array([p for _, p in H["ph"]] + [p for _, p in H["pl"]])
    sw_t = np.array([ci for ci, _ in H["ph"]] + [ci for ci, _ in H["pl"]])
    out = []
    for ev in events:
        i, d, price, a, lv = ev[:5]
        dist = -d * (price - H["c"][i])
        recent = swings[(sw_t <= i) & (sw_t > i - 240)]
        for _ in range(30):
            u = rng.uniform(0.5, 1.5) * a * (1 if rng.random() < 0.5 else -1)
            nd = dist + u
            if nd < 0.5 * a:
                continue
            fp = H["c"][i] - d * nd
            if len(recent) and np.min(np.abs(recent - fp)) < 0.3 * a:
                continue
            out.append((i, d, fp, a, fp) + ((("fake",) + tuple(ev[5][1:])),) if len(ev) > 5 else (i, d, fp, a, fp))
            break
    return out


def main():
    root, res = Path(sys.argv[1]), Path(sys.argv[2])
    t0 = time.time()
    h1, m30, m5 = load(root, res)
    H = prep_h1(h1)
    rng = np.random.default_rng(SEED)
    out = {"dữ liệu": {"H1": [str(pd.Timestamp(h1.time.iloc[0], unit="s")), str(pd.Timestamp(h1.time.iloc[-1], unit="s"))],
                       "M30": str(pd.Timestamp(m30.time.iloc[-1], unit="s"))}}
    ev = {v: candidates(H, Cfg(variant=v)) for v in ("F", "R")}
    trades = {v: run(H, m30, Cfg(variant=v), ev[v]) for v in ("F", "R")}
    # code check: replay the first filled F trade by hand on raw M30 bars
    q = trades["F"][0]
    k = int(np.searchsorted(m30["time"].to_numpy(), q["fill"]))
    hand_hit = None
    for j in range(k, len(m30)):
        hi, lo, sp = m30["high"].iat[j], m30["low"].iat[j], m30["sp"].iat[j]
        adv, fav = (lo, hi) if q["d"] == 1 else (hi + sp, lo + sp)
        if q["d"] * (adv - q["sl"]) <= 0:
            hand_hit = "SL"; break
        if q["d"] * (fav - q["tp"][0]) >= 0:
            hand_hit = "TP1"; break
    out["kiểm code: lệnh F đầu tiên"] = {"engine": q["reason"], "R": round(q["R"], 3), "tay (chạm đầu tiên)": hand_hit,
                                        "đặt": str(pd.Timestamp(q["place"], unit="s")), "khớp": str(pd.Timestamp(q["fill"], unit="s")), "giá": round(q["fill_px"], 2)}
    for v in ("F", "R"):
        out[v] = {"kỳ chọn": stats(trades[v], START, SPLIT), "kỳ kiểm": stats(trades[v], SPLIT, END), "cả kỳ": stats(trades[v]),
                  "số lệnh chờ đặt": len([e for e in ev[v] if START <= H["t"][e[0]] < END])}
        print(v, "| chọn", out[v]["kỳ chọn"], "\n   kiểm", out[v]["kỳ kiểm"], flush=True)
    sel = max(("F", "R"), key=lambda v: out[v]["kỳ chọn"].get("MAR") or -99)
    cfg = Cfg(variant=sel)
    tr = trades[sel]
    full, kk, ss = out[sel]["cả kỳ"], out[sel]["kỳ kiểm"], out[sel]["kỳ chọn"]
    ci = boot_ci(tr, rng)
    fakes = []
    for _ in range(RUNS):
        fakes.append(sum(q["R"] for q in run(H, m30, cfg, fake_events(H, ev[sel], rng)) if START <= q["place"] < END))
    mkt = run(H, m30, replace(cfg, market=True), ev[sel])
    nogate = run(H, m30, replace(cfg, gate=False), candidates(H, replace(cfg, gate=False)))
    harsh = run(H, m30, replace(cfg, cost_mult=1.5, swap_oz=SWAP_OZ * 1.5), ev[sel])
    nbs = [replace(cfg, sl_atr=1.0), replace(cfg, sl_atr=1.6), replace(cfg, off_atr=0.1), replace(cfg, off_atr=0.3),
           replace(cfg, expiry_h=12), replace(cfg, expiry_h=48)]
    nb_rows = []
    for x in nbs:
        tx_ = run(H, m30, x, candidates(H, x))
        s_ = stats(tx_, SPLIT, END)
        nb_rows.append({"cfg": {"sl": x.sl_atr, "off": x.off_atr, "exp": x.expiry_h}, "kỳ kiểm tổng R": s_["tổng R"], "n": s_["n"]})
    nb_ok = sum(1 for r in nb_rows if r["kỳ kiểm tổng R"] > 0)
    m5tr = run(H, m5, cfg, ev[sel])
    m5_from = pd.Timestamp("2024-06-01").value // 10**9
    lfx = [q for q in tr if q["place"] >= LFX_FROM]
    crit = {
        "1 kỳ kiểm R > 0, PF ≥ 1,2, ≥ 50 lệnh": kk["tổng R"] > 0 and (kk.get("PF") or 0) >= 1.2 and kk["n"] >= 50,
        "2 R TB > 0 hai kỳ, CI > 0": ss.get("R TB", -1) > 0 and kk.get("R TB", -1) > 0 and ci[0] > 0,
        "3 hơn p95 mức giả": full["tổng R"] > float(np.percentile(fakes, 95)),
        "4 hơn vào thị trường": full["R TB"] > stats(mkt).get("R TB", 9),
        "5 mua và bán ≥ −0,05": all((v[1] is None or v[0] < 15 or v[1] >= -0.05) for v in (full["mua: n / R TB"], full["bán: n / R TB"])),
        "6 chi phí × 1,5 vẫn > 0": stats(harsh)["tổng R"] > 0,
        "7 láng giềng ≥ 4/6": nb_ok >= 4,
        "8 DD ≤ 15 R": full["DD R"] <= 15,
    }
    out["được chọn"] = {"biến thể": sel, "CI R TB (α 2,5 %)": ci,
                        "mức giả tổng R p50 / p95": [round(float(np.percentile(fakes, 50)), 1), round(float(np.percentile(fakes, 95)), 1)],
                        "vào thị trường (C2)": stats(mkt), "bỏ cổng D1 (C3)": stats(nogate), "chi phí × 1,5": stats(harsh),
                        "láng giềng": nb_rows, "láng giềng đạt": f"{nb_ok}/6",
                        "theo năm": {str(y): stats(tr, pd.Timestamp(f"{y}-01-01").value // 10**9, pd.Timestamp(f"{y + 1}-01-01").value // 10**9).get("tổng R")
                                     for y in range(2018, 2027)},
                        "độ nhạy M5 (06/2024 →): M30 / M5": [stats(tr, m5_from).get("tổng R"), stats(m5tr, m5_from).get("tổng R")],
                        "lệnh rule 04–17/11/2026": [{"đặt (server)": str(pd.Timestamp(q["place"], unit="s")), "chiều": q["d"], "mức": round(q["price"], 1),
                                                     "SL": round(q["sl"], 1), "R": round(q["R"], 2), "lý do": q["reason"]} for q in lfx],
                        "tiêu chí": crit, "đạt": all(crit.values())}
    Path(res, "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    s = out["được chọn"]
    print("\nchosen", sel, "| CI", ci, "| fake p50/p95", s["mức giả tổng R p50 / p95"], "| full", full["tổng R"], "\n C2", s["vào thị trường (C2)"],
          "\n C3", s["bỏ cổng D1 (C3)"], "\n harsh", s["chi phí × 1,5"]["tổng R"], "| nb", nb_rows, "\n years", s["theo năm"], "\n M5", s["độ nhạy M5 (06/2024 →): M30 / M5"],
          "\n LFX window", s["lệnh rule 04–17/11/2026"], "\n crit", crit, "\n check", out["kiểm code: lệnh F đầu tiên"], "\n done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
