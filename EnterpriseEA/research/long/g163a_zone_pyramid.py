"""G163a: loose zone entries in the D1 regime direction (EMA band Z1, liquidity levels Z2, H4 Fib zone Z3) with in-profit pyramiding
(P0 none, P1 every +1R, P2 confirmed pullback to structure) vs random entries in the same regime and random-bar adds.
Plan: docs/superpowers/plans/2026-11-04-g163-loose-zone-pyramid.md (branch a).

Usage: g163a_zone_pyramid.py <data dir> <raw D1 csv> <out dir>
"""
import itertools
import json
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g158_hedge_recovery as g8  # noqa: E402
import g159a_modules as m9  # noqa: E402
import g160a_clue_screen as c0  # noqa: E402

START, SPLIT, END = g8.START, g8.SPLIT, g8.END
S_A, S_Z = g.ts(2010, 3, 1), g.ts(2018, 3, 1)
RISK = 0.005
COMM_OZ, SWAP_OZ = 0.06, 0.30          # 6 USD / lot round turn, 30 USD / lot / night, per ounce
SEED, BOOT, WEEK = 163, 2000, 7 * 86400


@dataclass(frozen=True)
class Cfg:
    zone: str = "Z1"
    pyr: str = "P0"
    zpad: float = 0.3                  # Z2 level band (ATR H1)
    slpad: float = 0.3                 # stop below the 3-bar low / pullback low (ATR)
    add_at: float = 1.0                # profit (R) before adds are allowed / P1 step
    cost_mult: float = 1.0
    swap_oz: float = SWAP_OZ
    rand_entry: float = 0.0            # > 0: random entries with this probability on flat regime bars (Z-rand)
    rand_add: float = 0.0              # > 0: random adds with this probability on eligible bars (P-rand)


def prep(B, piv_src):
    """Indicators shared by all runs: EMA21 / 55, confirmed 5/5 swing lows / highs (latest and list), ZigZag Fib zone."""
    h, l, c = B["h"], B["l"], B["c"]
    n = len(c)
    B["e21"], B["e55"] = g.ema(c, 21), g.ema(c, 55)
    sl_, sh_ = np.full(n, np.nan), np.full(n, np.nan)
    lows, highs = [], []
    cl = ch = np.nan
    for i in range(n):
        j = i - 5
        if j >= 5:
            if l[j] == l[j - 5:j + 6].min():
                cl = l[j]; lows.append((i, l[j]))
            if h[j] == h[j - 5:j + 6].max():
                ch = h[j]; highs.append((i, h[j]))
        sl_[i], sh_[i] = cl, ch
    B["swl"], B["swh"], B["lows"], B["highs"] = sl_, sh_, lows, highs
    # Fib zone of the latest confirmed ZigZag leg (2 ATR of the pivot frame), mapped to bars
    Hh, Hl, Ha, close_bar = piv_src
    piv = c0.zigzag(Hh, Hl, Ha, 2)
    flo, fhi, fdir = np.full(n, np.nan), np.full(n, np.nan), np.zeros(n, int)
    for a, b in zip(piv[:-1], piv[1:]):
        k = close_bar[b[3]] if b[3] < len(close_bar) else n
        if k >= n:
            continue
        lo, hi = min(a[1], b[1]), max(a[1], b[1])
        dirn = 1 if b[2] == 1 else -1              # leg ending at a high = up leg
        rngv = hi - lo
        z1, z2 = (hi - 0.618 * rngv, hi - 0.382 * rngv) if dirn == 1 else (lo + 0.382 * rngv, lo + 0.618 * rngv)
        flo[k:], fhi[k:], fdir[k:] = z1, z2, dirn
    B["flo"], B["fhi"], B["fdir"] = flo, fhi, fdir
    return B


def signal(B, i, d, cfg):
    o, h, l, c, A = B["o"], B["h"], B["l"], B["c"], B["atr"]
    ext = l[i] if d == 1 else h[i]
    if cfg.zone == "Z1":
        top, bot = max(B["e21"][i], B["e55"][i]), min(B["e21"][i], B["e55"][i])
        touched = l[i] <= top if d == 1 else h[i] >= bot           # the bar's extreme reached the EMA21-EMA55 band
        return touched and d * (c[i] - B["e21"][i]) > 0
    if cfg.zone == "Z2":
        lv = [B["pdl"][i], B["al"][i], B["swl"][i]] if d == 1 else [B["pdh"][i], B["ah"][i], B["swh"][i]]
        for v in lv:
            if np.isfinite(v) and abs(ext - v) <= cfg.zpad * A[i] and d * (c[i] - v) > 0:
                return True
        return False
    if cfg.zone == "Z3":
        if B["fdir"][i] != d or not np.isfinite(B["flo"][i]):
            return False
        return B["flo"][i] <= ext <= B["fhi"][i] and d * (c[i] - o[i]) > 0
    raise ValueError(cfg.zone)


def run(B, reg, cfg, start, end, rng=None, stats=None):
    t, o, h, l, c, sp, A = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["atr"]
    slip = 0.5 * B["sp_med"] * cfg.cost_mult
    comm = COMM_OZ * cfg.cost_mult
    i0, i1 = int(np.searchsorted(t, start)), int(np.searchsorted(t, end))
    trades = []
    pos = None
    pending = None
    cool = 0
    n_elig_e = n_elig_a = n_adds = 0

    def fill(d, p, spread):
        return p + spread + slip if d == 1 else p - slip

    def exit_px(d, p, spread):
        return p - slip if d == 1 else p + spread + slip

    def leg_r(leg, px, spread):
        d = pos["d"]
        pnl = d * (exit_px(d, px, spread) - leg["e"]) - comm - leg["swap"]
        return leg["share"] * pnl / leg["dist"]

    def open_risk():
        d = pos["d"]
        return sum(leg["share"] * d * (leg["e"] - leg["stop"]) / leg["dist"] for leg in pos["legs"])

    def add_leg(d, e, stop):
        dist = d * (e - stop)
        if dist <= 0:
            return False
        share = min(1.0, 1.0 - open_risk())
        if share < 0.05:
            return False
        pos["legs"].append({"e": e, "stop": stop, "dist": dist, "share": share, "swap": 0.0, "add": True})
        return True

    def close_all(px_of, reason):
        nonlocal pos
        base_r = add_r = 0.0
        for leg in pos["legs"]:
            r = leg_r(leg, px_of(leg), sp[i])
            if leg["add"]:
                add_r += r
            else:
                base_r += r
        for leg in pos["closed"]:
            if leg[0]:
                add_r += leg[1]
            else:
                base_r += leg[1]
        trades.append({"t_in": int(t[pos["i"]]), "t_out": int(t[i]), "d": pos["d"], "r": base_r + add_r, "r_base": base_r, "r_add": add_r,
                       "adds": pos["n_add"], "reason": reason})
        pos = None

    for i in range(max(i0, 6), i1):
        spread = sp[i]
        if pending is not None and pos is None:
            d, stop = pending
            e = fill(d, o[i], spread)
            dist = d * (e - stop)
            if 0.5 * A[i - 1] <= dist <= 3 * A[i - 1]:
                pos = {"d": d, "i": i, "legs": [{"e": e, "stop": stop, "dist": dist, "share": 1.0, "swap": 0.0, "add": False}],
                       "closed": [], "best": 0.0, "be": False, "n_add": 0, "next_p1": cfg.add_at}
            pending = None
        if pos is not None:
            d = pos["d"]
            base = pos["legs"][0] if not pos["legs"][0]["add"] else None
            if t[i] // 86400 != t[i - 1] // 86400:
                mult = 3 if ((t[i] // 86400) + 3) % 7 == 3 else 1
                for leg in pos["legs"]:
                    leg["swap"] += cfg.swap_oz * mult
            # adverse extreme: stops
            adv = l[i] if d == 1 else h[i]
            keep = []
            for leg in pos["legs"]:
                if d * (adv - leg["stop"]) <= 0:
                    px = o[i] if d * (o[i] - leg["stop"]) < 0 else leg["stop"]
                    pos["closed"].append((leg["add"], leg_r(leg, px, spread)))
                else:
                    keep.append(leg)
            pos["legs"] = keep
            if not any(not x["add"] for x in pos["legs"]):
                # base stopped: adds close with it at the same bar's close or their stop (whichever first already handled)
                if pos["legs"]:
                    close_all(lambda leg: c[i], "SL gốc")
                else:
                    close_all(lambda leg: c[i], "SL")
                cool = 3
                continue
            base = [x for x in pos["legs"] if not x["add"]][0]
            fav = h[i] if d == 1 else l[i]
            prof = d * (fav - base["e"]) / base["dist"]
            pos["best"] = max(pos["best"], prof)
            if pos["best"] >= 1.0 and not pos["be"]:
                base["stop"] = base["e"] + d * comm
                pos["be"] = True
            if cfg.pyr == "P1" and pos["n_add"] < 3 and pos["best"] >= pos["next_p1"]:
                lvl = base["e"] + d * pos["next_p1"] * base["dist"]
                stop = (l[i - 3:i].min() - cfg.slpad * A[i - 1]) if d == 1 else (h[i - 3:i].max() + cfg.slpad * A[i - 1])
                if add_leg(d, fill(d, lvl, spread), stop):
                    pos["n_add"] += 1
                pos["next_p1"] += 1.0
            # bar close: exits
            reason = None
            if pos["best"] >= 1.0 and d * (c[i] - B["e55"][i]) < 0:
                reason = "EMA55"
            elif i - pos["i"] >= 120:
                reason = "hết giờ"
            if reason:
                close_all(lambda leg: c[i], reason)
                cool = 3
                continue
            if pos["best"] >= 2.0:
                sw = B["swl"][i] if d == 1 else B["swh"][i]
                if np.isfinite(sw):
                    for leg in pos["legs"]:
                        if d * (sw - leg["stop"]) > 0 and d * (c[i] - sw) > 0:
                            leg["stop"] = sw
            # bar close: P2 / random adds
            if cfg.pyr in ("P2",) or cfg.rand_add > 0:
                elig = pos["be"] and pos["best"] >= cfg.add_at and pos["n_add"] < 3
                if elig:
                    n_elig_a += 1
                    do = False
                    if cfg.rand_add > 0:
                        do = rng.random() < cfg.rand_add
                    else:
                        rg = h[i] - l[i]
                        wick = (min(o[i], c[i]) - l[i]) if d == 1 else (h[i] - max(o[i], c[i]))
                        conf = rg > 0 and wick >= 0.5 * rg and d * (c[i] - o[i]) > 0
                        if conf:
                            ext = l[i] if d == 1 else h[i]
                            lv = [B["e21"][i], B["pdl"][i] if d == 1 else B["pdh"][i], B["al"][i] if d == 1 else B["ah"][i]]
                            # latest broken swing high (buy) / low (sell), now support / resistance
                            sw = B["swh"][i] if d == 1 else B["swl"][i]
                            if np.isfinite(sw) and d * (c[i] - sw) > 0:
                                lv.append(sw)
                            do = any(np.isfinite(v) and d * (ext - v) <= 0 < d * (c[i] - v) for v in lv)
                    if do:
                        stop = (l[i] - cfg.slpad * A[i]) if d == 1 else (h[i] + cfg.slpad * A[i])
                        if add_leg(d, fill(d, c[i], spread), stop):
                            pos["n_add"] += 1
                            n_adds += 1
        else:
            if cool > 0:
                cool -= 1
            d = int(reg[i])
            if d != 0 and cool == 0 and pending is None:
                n_elig_e += 1
                go = (rng.random() < cfg.rand_entry) if cfg.rand_entry > 0 else signal(B, i, d, cfg)
                if go:
                    stop = (l[i - 2:i + 1].min() - cfg.slpad * A[i]) if d == 1 else (h[i - 2:i + 1].max() + cfg.slpad * A[i])
                    pending = (d, stop)
    if stats is not None:
        stats.update(elig_e=n_elig_e, elig_a=n_elig_a, adds=n_adds, entries=len(trades))
    return trades


def metrics(tr, a, z):
    x = [q for q in tr if a <= q["t_in"] < z]
    if not x:
        return {"n": 0, "tổng R": 0.0}
    r = np.array([q["r"] for q in sorted(x, key=lambda q: q["t_out"])])
    eq = np.cumsum(r)
    dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    weeks = (z - a) / WEEK
    pos_, neg = r[r > 0].sum(), -r[r < 0].sum()
    reasons = {}
    for q in x:
        reasons[q["reason"]] = reasons.get(q["reason"], 0) + 1
    adds = [q for q in x if q["adds"]]
    return {"n": len(x), "lệnh / tuần": round(len(x) / weeks, 2), "tỷ lệ thắng": round(float(np.mean(r > 0)), 3), "R TB": round(float(r.mean()), 3),
            "PF": round(float(pos_ / neg), 2) if neg > 0 else None, "tổng R": round(float(r.sum()), 1), "DD R": round(dd, 1),
            "DD % vốn": round(dd * RISK * 100, 1), "MAR": round(float(r.sum()) / dd, 2) if dd > 0 else None,
            "R từ lệnh gốc": round(sum(q["r_base"] for q in x), 1), "R từ lệnh bồi": round(sum(q["r_add"] for q in x), 1),
            "số lần bồi": int(sum(q["adds"] for q in x)), "lệnh có bồi": len(adds),
            "mua R": round(sum(q["r"] for q in x if q["d"] == 1), 1), "bán R": round(sum(q["r"] for q in x if q["d"] == -1), 1),
            "lý do thoát": reasons}


def roll_dd(tr):
    hits = n = 0
    a = g.ts(2018, 5, 1)
    while a + 365 * 86400 <= END:
        m = metrics(tr, a, a + 365 * 86400)
        hits += m.get("DD % vốn", 0) >= 15
        n += 1
        a += 30 * 86400
    return round(hits / n, 3)


def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    D = g8.load_h1(root)
    F = g8.daily(D)
    H = g8.h4_frame(D)
    B = g8.bars_h1(D, F)
    B.update(pdl=F["pdl"], pdh=F["pdh"], al=F["al"], ah=F["ah"])
    close_bar = np.searchsorted(H["closed"], np.arange(1, len(H["c"]) + 1), side="left")
    B = prep(B, (H["h"], H["l"], H["atr"], close_bar))
    reg = F["reg"]
    rng = np.random.default_rng(SEED)
    res = {"tổ hợp": {}}
    trades = {}
    for z, p in itertools.product(("Z1", "Z2", "Z3"), ("P0", "P1", "P2")):
        cfg = Cfg(zone=z, pyr=p)
        tr = run(B, reg, cfg, START, END)
        trades[(z, p)] = tr
        row = {"kỳ chọn": metrics(tr, START, SPLIT), "kỳ kiểm": metrics(tr, SPLIT, END), "cả kỳ": metrics(tr, START, END)}
        res["tổ hợp"][f"{z}+{p}"] = row
        s, k = row["kỳ chọn"], row["kỳ kiểm"]
        print(z, p, "| chọn n", s["n"], "/tuần", s.get("lệnh / tuần"), "R", s["tổng R"], "DD", s.get("DD R"), "MAR", s.get("MAR"), "PF", s.get("PF"),
              "| kiểm R", k["tổng R"], "MAR", k.get("MAR"), "PF", k.get("PF"), "| bồi R", row["cả kỳ"].get("R từ lệnh bồi"),
              "| mua/bán", row["cả kỳ"].get("mua R"), row["cả kỳ"].get("bán R"), flush=True)
    cands = [(k, v) for k, v in res["tổ hợp"].items() if (v["kỳ chọn"].get("lệnh / tuần") or 0) >= 2 and v["kỳ chọn"].get("MAR") is not None]
    if not cands:
        res["kết luận"] = "không tổ hợp nào ≥ 2 lệnh / tuần ở kỳ chọn"
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        print("none selectable")
        return
    key, row = max(cands, key=lambda kv: kv[1]["kỳ chọn"]["MAR"])
    z, p = key.split("+")
    cfg = Cfg(zone=z, pyr=p)
    tr = trades[(z, p)]
    full, kk = row["cả kỳ"], row["kỳ kiểm"]
    st = {}
    run(B, reg, cfg, START, END, stats=st)
    # Z-rand: random entries in the regime at the same rate
    qe = st["entries"] / max(st["elig_e"], 1)
    zr = [metrics(run(B, reg, replace(cfg, rand_entry=qe), START, END, rng=rng), START, END)["tổng R"] for _ in range(50)]
    # adds useful?
    add_ci, prand = None, None
    if p != "P0":
        base = {q["t_in"]: q for q in trades[(z, "P0")]}
        diff = {}
        for q in tr:
            if q["t_in"] in base:
                w = q["t_in"] // WEEK
                diff[w] = diff.get(w, 0.0) + q["r"] - base[q["t_in"]]["r"]
        Wv = np.array(list(diff.values()))
        bs = [Wv[rng.integers(0, len(Wv), len(Wv))].sum() for _ in range(BOOT)]
        add_ci = [round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
        if p == "P2":
            qa = st["adds"] / max(st["elig_a"], 1)
            pr = [metrics(run(B, reg, replace(cfg, pyr="PR", rand_add=qa), START, END, rng=rng), START, END)["tổng R"] for _ in range(50)]
            prand = [float(np.percentile(pr, 50)), float(np.percentile(pr, 95))]
    harsh = metrics(run(B, reg, replace(cfg, cost_mult=1.5, swap_oz=2 * SWAP_OZ), START, END), START, END)
    rdd = roll_dd(tr)
    nbs = [replace(cfg, slpad=0.2), replace(cfg, slpad=0.5)]
    if z == "Z2":
        nbs += [replace(cfg, zpad=0.2), replace(cfg, zpad=0.4)]
    if p != "P0":
        nbs += [replace(cfg, add_at=0.75), replace(cfg, add_at=1.5)]
    nb_rows, nb_ok = [], 0
    for x in nbs:
        t_ = run(B, reg, x, START, END)
        mk, mf = metrics(t_, SPLIT, END), metrics(t_, START, END)
        good = mk["tổng R"] > 0 and (mk.get("PF") or 0) >= 1.2 and mf.get("DD % vốn", 99) <= 15
        nb_ok += good
        nb_rows.append({"slpad": x.slpad, "zpad": x.zpad, "add_at": x.add_at, "kỳ kiểm R": mk["tổng R"], "PF": mk.get("PF"),
                        "DD %": mf.get("DD % vốn"), "thỏa": good})
    # D1 stress
    Bd = m9.add_structure_d1(g8.bars_d1(raw_d1))
    Bd = prep(Bd, (Bd["h"], Bd["l"], Bd["atr"], np.arange(len(Bd["c"]))))
    Bd.update(pdl=np.r_[np.nan, Bd["l"][:-1]], pdh=np.r_[np.nan, Bd["h"][:-1]], al=np.full(len(Bd["c"]), np.nan), ah=np.full(len(Bd["c"]), np.nan))
    sd = metrics(run(Bd, Bd["reg"], cfg, S_A, S_Z), S_A, S_Z)
    crit = {
        "1 kỳ kiểm R > 0, PF ≥ 1,2": kk["tổng R"] > 0 and (kk.get("PF") or 0) >= 1.2,
        "2 ≥ 2 lệnh / tuần hai kỳ": (row["kỳ chọn"].get("lệnh / tuần") or 0) >= 2 and (kk.get("lệnh / tuần") or 0) >= 2,
        "3 DD ≤ 15 %, P(DD 12 tháng ≥ 15 %) ≤ 5 %": full.get("DD % vốn", 99) <= 15 and rdd <= 0.05,
        "4 hơn p95 Z-rand": full["tổng R"] > float(np.percentile(zr, 95)),
        "5 bồi có ích": True if p == "P0" else (add_ci[0] > 0 and (prand is None or full["tổng R"] > prand[1])),
        "6 mua và bán ≥ 0": full["mua R"] >= 0 and full["bán R"] >= 0,
        "7 chi phí khắc nghiệt R > 0": harsh["tổng R"] > 0,
        "8 láng giềng ≥ 2/3": nb_ok >= int(np.ceil(2 * len(nb_rows) / 3)),
        "9 stress D1: R ≥ 0, DD ≤ 25 %": sd["tổng R"] >= 0 and sd.get("DD % vốn", 99) <= 25,
    }
    res["được chọn"] = {"tổ hợp": key, "kỳ chọn": row["kỳ chọn"], "kỳ kiểm": kk, "cả kỳ": full, "P(DD 12 tháng ≥ 15 %)": rdd,
                        "Z-rand tổng R p50 / p95": [float(np.percentile(zr, 50)), float(np.percentile(zr, 95))],
                        "chênh do bồi: CI 95 %": add_ci, "P-rand tổng R p50 / p95": prand, "khắc nghiệt": harsh,
                        "láng giềng": nb_rows, "láng giềng đạt": f"{nb_ok}/{len(nb_rows)}", "stress D1 2010–2018": sd,
                        "tiêu chí": crit, "đạt": all(crit.values())}
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    s = res["được chọn"]
    print("chosen", key, "\n kiểm", kk, "\n full", full, "\n Z-rand", s["Z-rand tổng R p50 / p95"], "| add CI", add_ci, "| P-rand", prand,
          "\n harsh", harsh["tổng R"], "| 12m", rdd, "| nb", s["láng giềng đạt"], "\n stress", sd, "\n crit", crit, "\ndone", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
