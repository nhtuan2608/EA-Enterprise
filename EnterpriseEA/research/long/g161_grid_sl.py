"""G161: grid averaging with a basket stop loss (L x balance at basket open) plus continuous pair-off P1, vs a single trade with the
same maximum loss, random entries and P1 off. Plan: docs/superpowers/plans/2026-11-04-g161-grid-basket-sl.md.
With no stop and P1 off the engine reproduces G158 E4 (checked at start).

Usage: g161_grid_sl.py <data dir> <raw D1 csv> <out dir>
"""
import itertools
import json
import random
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g158_hedge_recovery as g8  # noqa: E402
import g159a_modules as m9  # noqa: E402

START, SPLIT, END = g8.START, g8.SPLIT, g8.END
CAPITAL, BASE_LOT, CONTRACT, COMM = g8.CAPITAL, g8.BASE_LOT, g8.CONTRACT, g8.COMM_PER_LOT
SEED = 161
S_A, S_Z = g.ts(2010, 3, 1), g.ts(2018, 3, 1)


@dataclass(frozen=True)
class Cfg:
    mult: float = 1.5
    step: float = 0.5
    levels: int = 6
    sl: float = 0.04            # basket stop: equity change since basket open <= -sl x balance at open; None = no stop
    p1: bool = True
    single: bool = False        # C1: one trade, stop = sl x balance, TP = 3 x stop distance
    swap: float = 30.0
    cost_mult: float = 1.0
    leverage: float = 500.0


def simulate(B, sig, cfg: Cfg, start, end):
    t, o, h, l, c, sp = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"]
    atr_d1 = B["atr_d1"]
    slip = 0.5 * B["sp_med"] * cfg.cost_mult
    comm = COMM * cfg.cost_mult
    bal = CAPITAL
    legs, runner = [], None
    S, last_add, tp_single, sl_single = 0.0, 0.0, None, None
    ruins, peak, mdd, max_lots, swap_paid = 0, CAPITAL, 0.0, 0.0, 0.0
    bal_start, pending = CAPITAL, None
    baskets = []                                   # (pnl, R money, reason)
    i0, i1 = int(np.searchsorted(t, start)), int(np.searchsorted(t, end))

    def xpx(side, p, spread):
        return (p - slip) if side == 1 else (p + spread + slip)

    def pnl_of(x, p, spread):
        return x[0] * (xpx(x[0], p, spread) - x[2]) * x[1] * CONTRACT

    def all_legs():
        return legs + ([[runner["side"], runner["lots"], runner["price"]]] if runner else [])

    def floating(p, spread):
        return sum(pnl_of(x, p, spread) for x in all_legs())

    def margin(p):
        al = all_legs()
        return max(sum(x[1] for x in al if x[0] == 1), sum(x[1] for x in al if x[0] == -1)) * CONTRACT * p / cfg.leverage

    def open_leg(side, lots, p, spread):
        nonlocal bal
        bal -= comm * lots
        return [side, lots, p + spread + slip if side == 1 else p - slip]

    def close_basket(reason):
        nonlocal bal_start
        baskets.append((bal - bal_start, (cfg.sl or 0) * bal_start, reason))
        bal_start = bal

    def stop_price(spread, p):
        """Price where equity - bal_start = -sl x bal_start (floating is linear in price while all legs share a side)."""
        thr = bal_start * (1 - cfg.sl)
        e0, e1 = bal + floating(p, spread), bal + floating(p + 1.0, spread)
        slope = e1 - e0
        return None if slope == 0 else p + (thr - e0) / slope

    for i in range(max(i0, 1), i1):
        spread = sp[i]
        if t[i] // 86400 != t[i - 1] // 86400:
            lots_open = sum(x[1] for x in all_legs())
            if lots_open:
                cost = cfg.swap * lots_open * (3 if ((t[i] // 86400) + 3) % 7 == 3 else 1)
                bal -= cost
                swap_paid += cost
        if pending is not None and not legs and runner is None:
            d = pending
            S = cfg.step * atr_d1[i] if np.isfinite(atr_d1[i]) else 0.0
            if S > 0:
                bal_start = bal
                legs = [open_leg(d, BASE_LOT, o[i], spread)]
                last_add = legs[0][2]
                if cfg.single:
                    dist = cfg.sl * bal_start / (BASE_LOT * CONTRACT)
                    sl_single, tp_single = o[i] - d * dist, o[i] + d * 3 * dist
            pending = None
        if legs or runner:
            side0 = legs[0][0] if legs else runner["side"]
            path = [l[i], h[i]] if side0 == 1 else [h[i], l[i]]
            for p in path:
                if cfg.single:
                    if not legs:
                        break
                    d = legs[0][0]
                    max_lots = max(max_lots, legs[0][1])
                    worst = sl_single if d * (p - sl_single) <= 0 else p
                    mdd = min(1.0, max(mdd, 1 - (bal + floating(worst, spread)) / peak))
                    hit = None
                    if d * (p - sl_single) <= 0:
                        hit = (o[i] if d * (o[i] - sl_single) < 0 else sl_single, "SL")
                    elif d * (p - tp_single) >= 0:
                        hit = (o[i] if d * (o[i] - tp_single) > 0 else tp_single, "TP")
                    if hit:
                        bal += pnl_of(legs[0], hit[0], spread)
                        legs = []
                        close_basket(hit[1])
                    continue
                stopped = False
                if legs and runner is None:
                    d = legs[0][0]
                    while len(legs) < cfg.levels and d * (p - (last_add - d * S)) <= 0:
                        lvl = last_add - d * S
                        if cfg.sl is not None:
                            sp_ = stop_price(spread, lvl)
                            if sp_ is not None and d * (lvl - sp_) <= 0:
                                break                       # the stop comes before this add
                        legs.append(open_leg(d, BASE_LOT * cfg.mult ** len(legs), lvl, spread))
                        last_add = lvl
                if runner is not None and runner["side"] * (p - runner["price"]) <= -S:
                    legs = [[runner["side"], runner["lots"], runner["price"]]]
                    last_add = runner["price"]
                    runner = None
                if cfg.sl is not None and (legs or runner):
                    d = (legs[0][0] if legs else runner["side"])
                    sp_ = stop_price(spread, p)
                    if sp_ is not None and d * (p - sp_) <= 0:
                        fill = o[i] if d * (o[i] - sp_) < 0 else sp_
                        bal += floating(fill, spread)
                        legs, runner = [], None
                        close_basket("SL")
                        stopped = True
                max_lots = max(max_lots, sum(x[1] for x in all_legs()))
                fl = floating(p, spread)
                eq = bal + fl
                mg = margin(p)
                mdd = min(1.0, max(mdd, 1 - eq / peak)) if peak > 0 else mdd
                if stopped:
                    break
                if eq <= 0 or (mg > 0 and eq / mg < 0.5):
                    ruins += 1
                    baskets.append((-bal_start, (cfg.sl or 0) * bal_start, "cháy"))
                    bal, legs, runner, pending = CAPITAL, [], None, None
                    bal_start, peak = CAPITAL, CAPITAL
                    break
                target = 0.5 * S * BASE_LOT * CONTRACT
                if legs and fl >= target:
                    win_side = 1 if p > legs[-1][2] else -1
                    cand = [x for x in legs if x[0] == win_side and pnl_of(x, p, spread) > 0]
                    keep = cand[-1] if cand else None
                    rest = [x for x in legs if x is not keep]
                    realized = sum(pnl_of(x, p, spread) for x in rest)
                    if keep is None or realized < 0:
                        bal += fl
                        legs = []
                        if runner is None:
                            close_basket("mục tiêu")
                    else:
                        bal += realized
                        runner = {"side": keep[0], "lots": keep[1], "price": keep[2], "tp": keep[2] + keep[0] * 3 * S}
                        legs = []
                if runner is not None and runner["side"] * (p - runner["tp"]) >= 0:
                    rs = runner["side"]
                    bal += rs * (xpx(rs, runner["tp"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                    runner = None
                    close_basket("lệnh chạy")
            if cfg.p1 and not cfg.single and runner is None and len(legs) >= 2:
                while len(legs) >= 2:
                    vals = [pnl_of(x, c[i], spread) for x in legs]
                    bi, wi = int(np.argmax(vals)), int(np.argmin(vals))
                    if bi == wi or vals[bi] <= 0 or vals[bi] + vals[wi] < 0:
                        break
                    bal += vals[bi] + vals[wi]
                    legs = [x for k, x in enumerate(legs) if k not in (bi, wi)]
                if not legs:
                    close_basket("cặp")
        peak = max(peak, bal + floating(c[i], sp[i]))
        if i in sig and not legs and runner is None and pending is None:
            pending = sig[i]
    final = bal + (floating(c[i1 - 1], sp[i1 - 1]) if (legs or runner) and i1 > 0 else 0.0)
    bp = np.array([b[0] for b in baskets]) if baskets else np.zeros(1)
    R = np.array([b[1] for b in baskets]) if baskets else np.ones(1)
    wins, losses = bp[bp > 0], bp[bp <= 0]
    gross = float(wins.sum())
    reasons = {}
    for b in baskets:
        reasons[b[2]] = reasons.get(b[2], 0) + 1
    net = final - CAPITAL * (1 + ruins)
    return {"cháy": ruins, "lãi ròng": round(net, 0), "DD lớn nhất": round(mdd, 3),
            "MAR": round(net / max(mdd, 1e-3) / CAPITAL, 2), "số rổ": len(baskets),
            "tỷ lệ rổ thắng": round(float(len(wins) / len(bp)), 3) if baskets else None,
            "lãi TB rổ thắng": round(float(wins.mean()), 0) if len(wins) else 0, "lỗ TB rổ thua": round(float(losses.mean()), 0) if len(losses) else 0,
            "PF": round(gross / abs(float(losses.sum())), 2) if losses.sum() < 0 else None,
            "kỳ vọng R": round(float(np.mean(bp / np.where(R > 0, R, np.nan))), 3) if cfg.sl and baskets else None,
            "lý do kết thúc": reasons, "lot mở tối đa": round(max_lots, 2), "swap / lãi gộp": round(swap_paid / gross, 3) if gross > 0 else None,
            "ES 5 % rổ": round(float(np.sort(bp)[:max(1, int(np.ceil(0.05 * len(bp))))].mean()), 0)}


def rolling(B, sig, cfg):
    ruin = dd30 = n = 0
    a = g.ts(2018, 5, 1)
    while a + 365 * 86400 <= END:
        x = simulate(B, sig, cfg, a, a + 365 * 86400)
        ruin += x["cháy"] > 0
        dd30 += x["DD lớn nhất"] >= 0.30
        n += 1
        a += 30 * 86400
    return round(ruin / n, 3), round(dd30 / n, 3)


def neighbours(cfg):
    ls = {0.02: (0.04,), 0.04: (0.02, 0.06), 0.06: (0.04,)}[cfg.sl]
    return [replace(cfg, sl=x) for x in ls] + [replace(cfg, step=1.0 if cfg.step == 0.5 else 0.5),
                                               replace(cfg, levels=4 if cfg.levels == 6 else 6),
                                               replace(cfg, mult=1.0 if cfg.mult == 1.5 else 1.5)]


def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    D = g8.load_h1(root)
    F = g8.daily(D)
    H = g8.h4_frame(D)
    B = g8.bars_h1(D, F)
    sig = {i: d for i, d in g8.entries(D, F, H)["E4"]}
    chk = simulate(B, sig, Cfg(mult=1.5, step=0.5, levels=10, sl=None, p1=False), START, SPLIT)
    ref = g8.simulate(B, sig, g8.Cfg(mech="R1", mult=1.5, step=0.5, levels=10, exit="X1"), START, SPLIT)
    same = (chk["cháy"], chk["lãi ròng"]) == (ref["cháy"], ref["lãi ròng (bỏ qua các lần nạp lại)"])
    print("check vs G158:", "khớp" if same else f"LỆCH {chk['lãi ròng']} vs {ref['lãi ròng (bỏ qua các lần nạp lại)']}", flush=True)
    res = {"kiểm code (không SL, không P1 = G158 E4)": bool(same), "cấu hình": [], "lệnh đơn C1": {}}
    for L in (0.02, 0.04, 0.06):
        c1 = Cfg(sl=L, single=True, p1=False)
        res["lệnh đơn C1"][f"L {L:.0%}"] = {"kỳ chọn": simulate(B, sig, c1, START, SPLIT), "kỳ kiểm": simulate(B, sig, c1, SPLIT, END)}
    grid = [Cfg(mult=m, levels=lv, step=s, sl=L) for m, lv, s, L in itertools.product((1.0, 1.5), (4, 6), (0.5, 1.0), (0.02, 0.04, 0.06))]
    for cfg in grid:
        sel = simulate(B, sig, cfg, START, SPLIT)
        res["cấu hình"].append({"cfg": {"mult": cfg.mult, "levels": cfg.levels, "step": cfg.step, "L": cfg.sl}, "kỳ chọn": sel})
        print(cfg.mult, cfg.levels, cfg.step, cfg.sl, "| chọn", sel["cháy"], sel["lãi ròng"], "DD", sel["DD lớn nhất"], "MAR", sel["MAR"],
              "PF", sel["PF"], "R", sel["kỳ vọng R"], sel["lý do kết thúc"], flush=True)
    ok = [(r, c) for r, c in zip(res["cấu hình"], grid) if r["kỳ chọn"]["cháy"] == 0 and r["kỳ chọn"]["lãi ròng"] > 0]
    if not ok:
        res["kết luận"] = "không cấu hình nào 0 cháy và lãi > 0 ở kỳ chọn"
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
        print("none selectable")
        return
    row, cfg = max(ok, key=lambda rc: rc[0]["kỳ chọn"]["MAR"])
    kk = simulate(B, sig, cfg, SPLIT, END)
    full = simulate(B, sig, cfg, START, END)
    harsh = simulate(B, sig, replace(cfg, swap=60.0, cost_mult=1.5), START, END)
    rr, dd30 = rolling(B, sig, cfg)
    Bd = m9.add_structure_d1(g8.bars_d1(raw_d1))
    rng = random.Random(SEED)
    sidx = list(np.nonzero((Bd["t"] >= S_A) & (Bd["t"] < S_Z))[0])
    st = [simulate(Bd, {int(i): rng.choice((1, -1)) for i in rng.sample(sidx, 60)}, cfg, S_A, S_Z) for _ in range(20)]
    c1k = res["lệnh đơn C1"][f"L {cfg.sl:.0%}"]["kỳ kiểm"]
    valid = list(np.nonzero((D["t"] >= START) & (D["t"] < END))[0])
    n_sig = len([1 for i in sig if START <= D["t"][i] < END])
    ctl = [simulate(B, {int(i): rng.choice((1, -1)) for i in rng.sample(valid, n_sig)}, cfg, START, END) for _ in range(50)]
    cp = [x["lãi ròng"] for x in ctl]
    nb = [(simulate(B, sig, x, START, SPLIT), simulate(B, sig, x, SPLIT, END)) for x in neighbours(cfg)]
    nb_ok = 0
    nb_rows = []
    for x_cfg, (a, b) in zip(neighbours(cfg), nb):
        fx = simulate(B, sig, x_cfg, START, END)
        good = b["cháy"] == 0 and b["lãi ròng"] > 0 and (b["PF"] or 0) >= 1.1 and fx["DD lớn nhất"] < 0.30
        nb_ok += good
        nb_rows.append({"cfg": {"mult": x_cfg.mult, "levels": x_cfg.levels, "step": x_cfg.step, "L": x_cfg.sl}, "kỳ kiểm": b,
                        "DD cả kỳ": fx["DD lớn nhất"], "thỏa 1 và 2": good})
    no_p1 = {"kỳ chọn": simulate(B, sig, replace(cfg, p1=False), START, SPLIT), "kỳ kiểm": simulate(B, sig, replace(cfg, p1=False), SPLIT, END),
             "cả kỳ": simulate(B, sig, replace(cfg, p1=False), START, END)}
    crit = {
        "1 kỳ kiểm 0 cháy, lãi > 0, PF ≥ 1,1": kk["cháy"] == 0 and kk["lãi ròng"] > 0 and (kk["PF"] or 0) >= 1.1,
        "2 DD < 30 %": full["DD lớn nhất"] < 0.30,
        "3 cháy 12 tháng = 0, DD ≥ 30 % ≤ 5 %": rr == 0 and dd30 <= 0.05,
        "4 khắc nghiệt lãi > 0": harsh["lãi ròng"] > 0,
        "5 stress 0 cháy, DD trung vị < 30 %": sum(x["cháy"] > 0 for x in st) == 0 and float(np.median([x["DD lớn nhất"] for x in st])) < 0.30,
        "6 MAR kỳ kiểm > lệnh đơn": kk["MAR"] > c1k["MAR"],
        "7 hơn p95 ngẫu nhiên": full["lãi ròng"] > float(np.percentile(cp, 95)),
        "8 láng giềng ≥ 2/3": nb_ok >= int(np.ceil(2 * len(nb) / 3)),
    }
    res["được chọn"] = {
        "cfg": row["cfg"], "kỳ chọn": row["kỳ chọn"], "kỳ kiểm": kk, "cả kỳ": full, "khắc nghiệt": harsh,
        "cháy 12 tháng": rr, "DD 12 tháng ≥ 30 %": dd30,
        "stress: lần cháy / 20": sum(x["cháy"] > 0 for x in st), "stress DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in st])), 3),
        "stress lãi ròng trung vị": float(np.median([x["lãi ròng"] for x in st])),
        "lệnh đơn C1 kỳ kiểm": c1k,
        "ngẫu nhiên C2": {"lãi ròng p50 / p95": [float(np.percentile(cp, 50)), float(np.percentile(cp, 95))],
                          "% lần chạy có cháy": round(float(np.mean([x["cháy"] > 0 for x in ctl])), 2),
                          "DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in ctl])), 3)},
        "tắt P1 (C3)": no_p1, "láng giềng": nb_rows, "láng giềng đạt": f"{nb_ok}/{len(nb)}",
        "tiêu chí": crit, "đạt": all(crit.values())}
    for r, c in zip(res["cấu hình"], grid):
        r["kỳ kiểm (chỉ báo cáo)"] = simulate(B, sig, c, SPLIT, END)
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("chosen", row["cfg"], "| kiểm", kk, "\n full", full, "\n crit", crit, "\n C1", c1k, "\n C2", res["được chọn"]["ngẫu nhiên C2"],
          "\n stress", res["được chọn"]["stress: lần cháy / 20"], res["được chọn"]["stress DD trung vị"], "| 12th", rr, dd30,
          "\n noP1 kiểm", no_p1["kỳ kiểm"]["lãi ròng"], no_p1["kỳ kiểm"]["MAR"], "| nb", nb_ok, len(nb), "\ndone", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
