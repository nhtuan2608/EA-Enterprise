"""G159a: mechanism modules on the G158 E4 base - no adds against the D1 regime (F1), lock on a D1 flip (H1) or an H4 structure
break (H2), margin floor for adds (F5), lot cap (F6), continuous pair-off (P1). Plan: docs/superpowers/plans/2026-11-04-g159a-mechanism-modules.md.
With every module off the engine reproduces G158 (checked at start).

Usage: g159a_modules.py <data dir> <raw D1 csv> <out dir>
"""
import itertools
import json
import random
import sys
import time
from dataclasses import dataclass, replace, asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g158_hedge_recovery as g8  # noqa: E402

START, SPLIT, END = g8.START, g8.SPLIT, g8.END
CAPITAL, BASE_LOT, CONTRACT, COMM = g8.CAPITAL, g8.BASE_LOT, g8.CONTRACT, g8.COMM_PER_LOT
MODULES = ("F1", "H1", "H2", "F5", "F6", "P1")
SEED = 159


@dataclass(frozen=True)
class Cfg:
    mech: str = "R1"
    mult: float = 1.5
    step: float = 0.5
    levels: int = 10
    exit: str = "X1"
    leverage: float = 500.0
    swap: float = 30.0
    cost_mult: float = 1.0
    mods: tuple = ()


def swings(h, l, k=3):
    """Latest confirmed pivot low / high (k bars each side) known at each bar's close."""
    n = len(h)
    lo, hi = np.full(n, np.nan), np.full(n, np.nan)
    cl, ch = np.nan, np.nan
    for i in range(n):
        j = i - k
        if j >= k:
            if l[j] == l[j - k:j + k + 1].min():
                cl = l[j]
            if h[j] == h[j - k:j + k + 1].max():
                ch = h[j]
        lo[i], hi[i] = cl, ch
    return lo, hi


def add_structure_h1(B, D, H, F):
    """Per H1 bar: D1 regime, H4 swing levels and the H4 close when an H4 bar has just closed."""
    lo4, hi4 = swings(H["h"], H["l"], 3)
    closed = H["closed"]
    n = len(D["t"])
    sw_lo, sw_hi, h4c = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for i in range(n):
        k = closed[i] - 1
        if k >= 0:
            sw_lo[i], sw_hi[i] = lo4[k], hi4[k]
            if i == 0 or closed[i] != closed[i - 1]:
                h4c[i] = H["c"][k]
    B.update(reg=F["reg"], sw_lo=sw_lo, sw_hi=sw_hi, struct_close=h4c)
    return B


def add_structure_d1(B):
    c = B["c"]
    e50 = g.ema(c, 50)
    reg = np.zeros(len(c), int)
    for k in range(61, len(c)):
        # regime of the previous closed day
        if c[k - 1] > e50[k - 1] and e50[k - 1] > e50[k - 11]:
            reg[k] = 1
        elif c[k - 1] < e50[k - 1] and e50[k - 1] < e50[k - 11]:
            reg[k] = -1
    lo, hi = swings(B["h"], B["l"], 3)
    B.update(reg=reg, sw_lo=lo, sw_hi=hi, struct_close=c.copy())
    return B


def simulate(B, sig, cfg: Cfg, start, end):
    t, o, h, l, c, sp, atr_b = B["t"], B["o"], B["h"], B["l"], B["c"], B["sp"], B["atr"]
    atr_d1, e55, e100 = B["atr_d1"], B["ema55"], B["ema100"]
    reg, sw_lo, sw_hi, sclose = B["reg"], B["sw_lo"], B["sw_hi"], B["struct_close"]
    M = set(cfg.mods)
    slip = 0.5 * B["sp_med"] * cfg.cost_mult
    comm = COMM * cfg.cost_mult
    bal = CAPITAL
    legs, runner, hedge = [], None, None
    S, last_add, lock_level = 0.0, 0.0, None
    ruins, ruin_times = 0, []
    peak, mdd = CAPITAL, 0.0
    max_lots, max_legs, swap_paid, baskets, worst_fl = 0.0, 0, 0.0, 0, 0.0
    basket_pnl, bal_start = [], CAPITAL
    pending = None
    i0, i1 = int(np.searchsorted(t, start)), int(np.searchsorted(t, end))

    def xpx(side, p, spread):
        return (p - slip) if side == 1 else (p + spread + slip)

    def pnl_of(x, p, spread):
        return x[0] * (xpx(x[0], p, spread) - x[2]) * x[1] * CONTRACT

    def all_legs():
        out = list(legs)
        if runner:
            out.append([runner["side"], runner["lots"], runner["price"]])
        if hedge:
            out.append(hedge)
        return out

    def floating(p, spread):
        return sum(pnl_of(x, p, spread) for x in all_legs())

    def margin(p):
        al = all_legs()
        lg = sum(x[1] for x in al if x[0] == 1)
        sh = sum(x[1] for x in al if x[0] == -1)
        return max(lg, sh) * CONTRACT * p / cfg.leverage

    def open_leg(side, lots, p, spread):
        nonlocal bal
        bal -= comm * lots
        return [side, lots, p + spread + slip if side == 1 else p - slip]

    def basket_closed():
        nonlocal bal_start
        if not legs and runner is None and hedge is None:
            basket_pnl.append(bal - bal_start)
            bal_start = bal

    for i in range(max(i0, 1), i1):
        spread = sp[i]
        if t[i] // 86400 != t[i - 1] // 86400:
            lots_open = sum(x[1] for x in all_legs())
            if lots_open:
                mult = 3 if ((t[i] // 86400) + 3) % 7 == 3 else 1
                cost = cfg.swap * lots_open * mult
                bal -= cost
                swap_paid += cost
        if pending is not None and not legs and runner is None and hedge is None:
            d = pending
            S = cfg.step * atr_d1[i] if np.isfinite(atr_d1[i]) else 0.0
            if S > 0:
                bal_start = bal
                legs = [open_leg(d, BASE_LOT, o[i], spread)]
                last_add = legs[0][2]
                baskets += 1
                lock_level = sw_lo[i] if d == 1 else sw_hi[i]
            pending = None
        if legs or runner or hedge:
            side0 = legs[0][0] if legs else (runner["side"] if runner else -hedge[0])
            path = [l[i], h[i]] if side0 == 1 else [h[i], l[i]]
            ruined = False
            for p in path:
                if legs and runner is None and hedge is None:
                    d = legs[0][0]
                    while len(legs) < cfg.levels and d * (p - (last_add - d * S)) <= 0:
                        lvl = last_add - d * S
                        lots = BASE_LOT * cfg.mult ** len(legs)
                        blocked = False
                        if "F1" in M and reg[i] == -d:
                            blocked = True
                        if "F6" in M and sum(x[1] for x in legs) + lots > 1.0 + 1e-9:
                            blocked = True
                        if "F5" in M:
                            mg = margin(lvl) + lots * CONTRACT * lvl / cfg.leverage
                            if mg > 0 and (bal + floating(lvl, spread)) / mg < 3.0:
                                blocked = True
                        if blocked:
                            last_add = lvl                          # the level is used up; the next add is one step further
                            continue
                        legs.append(open_leg(d, lots, lvl, spread))
                        last_add = lvl
                if runner is not None and runner["side"] * (p - runner["price"]) <= -S:
                    legs = [[runner["side"], runner["lots"], runner["price"]]]
                    last_add = runner["price"]
                    runner = None
                lots_now = sum(x[1] for x in all_legs())
                max_lots = max(max_lots, lots_now)
                max_legs = max(max_legs, len(legs))
                fl = floating(p, spread)
                worst_fl = min(worst_fl, fl)
                eq = bal + fl
                mg = margin(p)
                mdd = min(1.0, max(mdd, 1 - eq / peak)) if peak > 0 else mdd
                if eq <= 0 or (mg > 0 and eq / mg < 0.5):
                    ruins += 1
                    ruin_times.append(int(t[i]))
                    basket_pnl.append(-(bal_start))
                    bal, legs, runner, hedge, pending = CAPITAL, [], None, None, None
                    bal_start, peak = CAPITAL, CAPITAL
                    ruined = True
                    break
                target = 0.5 * S * BASE_LOT * CONTRACT
                if hedge is not None and floating(p, spread) >= target:
                    bal += floating(p, spread)
                    legs, runner, hedge = [], None, None
                    basket_closed()
                    break
                if legs and hedge is None and floating(p, spread) >= target:
                    if cfg.exit == "X0":
                        bal += floating(p, spread)
                        legs = []
                    else:
                        win_side = 1 if p > legs[-1][2] else -1
                        cand = [x for x in legs if x[0] == win_side and pnl_of(x, p, spread) > 0]
                        keep = cand[-1] if cand else None
                        rest = [x for x in legs if x is not keep]
                        realized = sum(pnl_of(x, p, spread) for x in rest)
                        if keep is None or realized < 0:
                            bal += floating(p, spread)
                            legs = []
                        else:
                            bal += realized
                            runner = {"side": keep[0], "lots": keep[1], "price": keep[2], "best": p,
                                      "tp": keep[2] + keep[0] * 3 * S, "be": False}
                            legs = []
                    basket_closed()
                if runner is not None:
                    rs = runner["side"]
                    if cfg.exit == "X1" and rs * (p - runner["tp"]) >= 0:
                        bal += rs * (xpx(rs, runner["tp"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                        runner = None
                        basket_closed()
                    elif cfg.exit == "X4" and runner["be"] and rs * (p - runner["price"]) <= 0:
                        bal += rs * (xpx(rs, runner["price"], spread) - runner["price"]) * runner["lots"] * CONTRACT
                        runner = None
                        basket_closed()
            if not ruined:
                # bar-close modules: lock / unlock, pair-off
                if legs and hedge is None and ("H1" in M or "H2" in M):
                    d = legs[0][0]
                    trig = False
                    if "H1" in M and reg[i] == -d:
                        trig = True
                    if "H2" in M and np.isfinite(sclose[i]) and lock_level is not None and np.isfinite(lock_level) and \
                            d * (sclose[i] - lock_level) < 0:
                        trig = True
                    if trig:
                        hedge = open_leg(-d, sum(x[1] for x in legs), c[i], spread)
                elif hedge is not None and legs:
                    d = legs[0][0]
                    unlock = pnl_of(hedge, c[i], spread) >= S * hedge[1] * CONTRACT
                    if "H1" in M and reg[i] != -d:
                        unlock = True
                    if "H2" in M and np.isfinite(sclose[i]) and lock_level is not None and d * (sclose[i] - lock_level) > 0:
                        unlock = True
                    if unlock:
                        bal += pnl_of(hedge, c[i], spread)
                        hedge = None
                        last_add = c[i]
                        lock_level = sw_lo[i] if d == 1 else sw_hi[i]
                if "P1" in M and hedge is None and len(legs) >= 2:
                    while len(legs) >= 2:
                        vals = [pnl_of(x, c[i], spread) for x in legs]
                        bi, wi = int(np.argmax(vals)), int(np.argmin(vals))
                        if bi == wi or vals[bi] <= 0 or vals[bi] + vals[wi] < 0:
                            break
                        bal += vals[bi] + vals[wi]
                        legs = [x for k, x in enumerate(legs) if k not in (bi, wi)]
                    if legs:
                        last_add = legs[-1][2] if legs[0][0] * (legs[-1][2] - last_add) < 0 else last_add
                    basket_closed()
        if runner is not None:
            rs = runner["side"]
            runner["best"] = max(runner["best"], c[i]) if rs == 1 else min(runner["best"], c[i])
            runner["be"] = True
            done = False
            if cfg.exit in ("X2", "X4") and rs * (c[i] - runner["best"]) <= -3 * atr_b[i]:
                done = True
            if cfg.exit == "X3":
                ema = e100[i] if rs * (c[i] - runner["price"]) >= 3 * S else e55[i]
                done = rs * (c[i] - ema) < 0
            if done:
                bal += rs * (xpx(rs, c[i], spread) - runner["price"]) * runner["lots"] * CONTRACT
                runner = None
                basket_closed()
        eq = bal + floating(c[i], spread)
        peak = max(peak, eq)
        if i in sig and not legs and runner is None and hedge is None and pending is None:
            pending = sig[i]
    final = bal + (floating(c[i1 - 1], sp[i1 - 1]) if (legs or runner or hedge) and i1 > 0 else 0.0)
    bp = np.array(basket_pnl) if basket_pnl else np.zeros(1)
    worst = np.sort(bp)[:max(1, int(np.ceil(0.05 * len(bp))))]
    gross = float(bp[bp > 0].sum())
    return {"cháy": ruins, "lúc cháy": ruin_times[:10], "lãi ròng": round(final - CAPITAL * (1 + ruins), 0),
            "DD lớn nhất": round(mdd, 3), "lot mở tối đa": round(max_lots, 2), "số lệnh tối đa": max_legs,
            "swap đã trả": round(swap_paid, 0), "số rổ": baskets, "thả nổi tệ nhất": round(worst_fl, 0),
            "ES 5 % rổ": round(float(worst.mean()), 0), "lãi gộp rổ có lời": round(gross, 0),
            "swap / lãi gộp": round(swap_paid / gross, 3) if gross > 0 else None}


def rolling_ruin(B, sig, cfg):
    hits = n = 0
    a = g.ts(2018, 5, 1)
    while a + 365 * 86400 <= END:
        hits += simulate(B, sig, cfg, a, a + 365 * 86400)["cháy"] > 0
        n += 1
        a += 30 * 86400
    return round(hits / n, 3)


def neighbours(cfg):
    out = [replace(cfg, step=1.0 if cfg.step == 0.5 else 0.5), replace(cfg, levels=6 if cfg.levels == 10 else 10)]
    out += [replace(cfg, mult=m) for m in (1.0, 2.0) if m != cfg.mult]
    return out


def main():
    root, raw_d1, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    g.HERE = root.parent
    t0 = time.time()
    D = g8.load_h1(root)
    F = g8.daily(D)
    H = g8.h4_frame(D)
    fams = g8.entries(D, F, H)
    B = add_structure_h1(g8.bars_h1(D, F), D, H, F)
    sig = {i: d for i, d in fams["E4"]}
    # code check: modules off == G158 E4 best configuration
    base = Cfg()
    mine = simulate(B, sig, base, START, SPLIT)
    ref = g8.simulate(B, sig, g8.Cfg(mech="R1", mult=1.5, step=0.5, levels=10, exit="X1"), START, SPLIT)
    same = (mine["cháy"], mine["lãi ròng"], mine["DD lớn nhất"]) == (ref["cháy"], ref["lãi ròng (bỏ qua các lần nạp lại)"], ref["DD lớn nhất"])
    print("check vs G158:", "khớp" if same else f"LỆCH {mine} vs {ref}", flush=True)
    res = {"kiểm code (nền = G158 E4)": bool(same), "cấu hình": []}
    combos = [()] + [(m,) for m in MODULES] + [c for k in (2, 3) for c in itertools.combinations(MODULES, k) if not {"H1", "H2"} <= set(c)]
    Bd = add_structure_d1(g8.bars_d1(raw_d1))
    rng = random.Random(SEED)
    sidx = list(np.nonzero((Bd["t"] >= g.ts(2010, 3, 1)) & (Bd["t"] < g.ts(2018, 3, 1)))[0])
    stress_sets = [{int(i): rng.choice((1, -1)) for i in rng.sample(sidx, 60)} for _ in range(20)]
    base_es = None
    for mods in combos:
        cfg = replace(base, mods=mods)
        sel = simulate(B, sig, cfg, START, SPLIT)
        chk = simulate(B, sig, cfg, SPLIT, END)
        full = simulate(B, sig, cfg, START, END)
        if base_es is None:
            base_es = full["ES 5 % rổ"]
        harsh = simulate(B, sig, replace(cfg, swap=60.0, cost_mult=1.5), START, END)
        rr = rolling_ruin(B, sig, cfg)
        st = [simulate(Bd, s, cfg, g.ts(2010, 3, 1), g.ts(2018, 3, 1)) for s in stress_sets]
        st_ruin = sum(1 for x in st if x["cháy"] > 0)
        nb = [(simulate(B, sig, x, START, SPLIT), simulate(B, sig, x, SPLIT, END)) for x in neighbours(cfg)]
        nb_ok = sum(1 for a, b in nb if a["cháy"] == 0 and b["cháy"] == 0 and a["lãi ròng"] > 0 and b["lãi ròng"] > 0)
        crit = {
            "1 hai kỳ 0 cháy, lãi > 0": sel["cháy"] == 0 and chk["cháy"] == 0 and sel["lãi ròng"] > 0 and chk["lãi ròng"] > 0,
            "2 cháy 12 tháng = 0": rr == 0,
            "3 DD < 50 %": full["DD lớn nhất"] < 0.5,
            "4 khắc nghiệt 0 cháy, lãi > 0": harsh["cháy"] == 0 and harsh["lãi ròng"] > 0,
            "5 stress 0 cháy": st_ruin == 0,
            "6 láng giềng ≥ 2/3": nb_ok >= int(np.ceil(2 * len(nb) / 3)),
            "7 ES không tệ hơn nền": full["ES 5 % rổ"] >= base_es,
            "8 swap ≤ 30 % lãi gộp": full["swap / lãi gộp"] is not None and full["swap / lãi gộp"] <= 0.30,
        }
        row = {"module": list(mods) or ["nền"], "kỳ chọn": sel, "kỳ kiểm": chk, "cả kỳ": full, "khắc nghiệt": harsh,
               "cháy 12 tháng": rr, "stress: số lần chạy cháy / 20": st_ruin,
               "stress DD trung vị": round(float(np.median([x["DD lớn nhất"] for x in st])), 3),
               "láng giềng đạt": f"{nb_ok}/{len(nb)}", "tiêu chí": crit, "đạt": all(crit.values())}
        res["cấu hình"].append(row)
        print("+".join(mods) or "nền", "| chọn", sel["cháy"], sel["lãi ròng"], "| kiểm", chk["cháy"], chk["lãi ròng"], "| DD", full["DD lớn nhất"],
              "| 12th", rr, "| stress", st_ruin, "| nb", row["láng giềng đạt"], "| ES", full["ES 5 % rổ"], "| swap%", full["swap / lãi gộp"],
              "| ĐẠT" if row["đạt"] else "", flush=True)
        (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    # random-entry control for passing configurations (or the best by full-period profit if none passes)
    passing = [r for r in res["cấu hình"] if r["đạt"]]
    targets = passing or sorted(res["cấu hình"], key=lambda r: -r["cả kỳ"]["lãi ròng"])[:1]
    valid = list(np.nonzero((D["t"] >= START) & (D["t"] < END))[0])
    for r in targets:
        cfg = replace(base, mods=tuple(m for m in r["module"] if m != "nền"))
        n = len([1 for i in sig if START <= D["t"][i] < END])
        ctrl = [simulate(B, {int(i): rng.choice((1, -1)) for i in rng.sample(valid, n)}, cfg, START, END) for _ in range(50)]
        cp = [x["lãi ròng"] for x in ctrl]
        r["ngẫu nhiên cùng module"] = {"lãi ròng p50 / p95": [float(np.percentile(cp, 50)), float(np.percentile(cp, 95))],
                                        "% lần chạy có cháy": round(float(np.mean([x["cháy"] > 0 for x in ctrl])), 2),
                                        "entry E4 hơn ngẫu nhiên": bool(r["cả kỳ"]["lãi ròng"] > np.percentile(cp, 95))}
        print("ctrl", r["module"], r["ngẫu nhiên cùng module"], flush=True)
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
