"""G73: earlier entries for S07 (DMI + EMA compression, XAUUSD). Pre-registered plan:
docs/superpowers/plans/2026-10-10-g73-early-entry.md. MT5 data only.

  python g73_early.py

B0 base (entry at the next main bar open), V1 intrabar trigger (the main-bar rule re-evaluated at every closed
sub-bar with the forming bar's provisional values), V2 stop order at the compression box / EMA ribbon edge.
All three are simulated on the same sub-bars: stop and target on sub-bars, the EMA exit on main-bar closes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402  (harsh, dd_p90)

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g73-early-entry.md"
SEC = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}
MAIN = {"M15": dict(comp=16, cool=8, hold=480), "M30": dict(comp=8, cool=4, hold=240), "H1": dict(comp=4, cool=2, hold=120)}
ADX_LOW, DI_GAP, ADX_RISE, BUF, SMIN, SMAX, TARGET, SWITCH = 20.0, 6.0, 10.0, 0.1, 1.0, 4.0, 8.0, 3.0
GAP = 6 * 3600
KEYS = ("train", "validate", "test", "examples")
DECIDE = ("train", "validate", "test")
RUNS = 200
N_TESTS = 12
EXAMPLES = [("Bán 23/9", -1, "2026-09-23T05:00", "2026-09-23T16:00"), ("Bán 25–28/9", -1, "2026-09-25T20:00", "2026-09-28T12:00"),
            ("Mua 05/8", 1, "2026-08-05T06:00", "2026-08-05T12:00"), ("Mua 19/8", 1, "2026-08-19T14:00", "2026-08-19T22:00")]


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
_CTX: dict = {}


def context(main: str, sub: str) -> dict:
    key = (main, sub)
    if key in _CTX:
        return _CTX[key]
    g.set_tf(sub)
    S = g.load("XAUUSD")
    g.set_tf(main)
    g.COMP_BARS = MAIN[main]["comp"]
    P = g.load("XAUUSD")
    P["pdms"] = P["pdi"] * P["atr"] / 100.0
    P["mdms"] = P["mdi"] * P["atr"] / 100.0
    P["gap"] = P["pdi"] - P["mdi"]
    P["ehi"] = np.maximum.reduce([P["E"][n] for n in (21, 55, 100, 200)])
    P["elo"] = np.minimum.reduce([P["E"][n] for n in (21, 55, 100, 200)])
    ps = SEC[main]
    pos = {int(t): k for k, t in enumerate(P["t"])}
    bucket = S["t"] - S["t"] % ps
    par = np.array([pos.get(int(b), -1) for b in bucket], dtype=np.int64)
    ns = len(par)
    last = np.zeros(ns, dtype=bool)
    last[:-1] = bucket[1:] != bucket[:-1]
    last[-1] = True
    first_sub = np.full(len(P["t"]), -1, dtype=np.int64)
    last_sub = np.full(len(P["t"]), -1, dtype=np.int64)
    for k in range(ns):
        p = par[k]
        if p < 0:
            continue
        if first_sub[p] < 0:
            first_sub[p] = k
        last_sub[p] = k
    # sub-bars agree with the main bars they build (close of the last sub-bar = main close)
    ok = [abs(S["c"][last_sub[p]] - P["c"][p]) < 1e-6 for p in range(len(P["t"])) if last_sub[p] >= 0]
    ctx = dict(main=main, sub=sub, P=P, S=S, par=par, last=last, first=first_sub, lastsub=last_sub,
               agree=float(np.mean(ok)) if ok else 0.0, start=int(S["utc"][0]), **MAIN[main])
    _CTX[key] = ctx
    return ctx


def period(utc: int) -> str:
    return g.period_of(utc)


# ---------------------------------------------------------------------------
# simulation on sub-bars
# ---------------------------------------------------------------------------
def walk(ctx, e, entry, d, dist, fill_bar=False):
    """Trade from sub-bar e at `entry`. fill_bar: e is the stop-order fill bar (only the stop is checked on it)."""
    P, S, par, last = ctx["P"], ctx["S"], ctx["par"], ctx["last"]
    o, hh, ll, c, sp = S["o"], S["h"], S["l"], S["c"], S["sp"]
    ns = len(c)
    sl, tp = entry - d * dist, entry + d * TARGET * dist
    best, nb = entry, 0
    exit_px, x, reason = None, None, "TIME"
    for j in range(e, ns):
        sj = sp[j] if d == -1 else 0.0
        bh, bl, bo = hh[j] + sj, ll[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px = sl if (fill_bar and j == e) else (min(sl, bo) if d == 1 else max(sl, bo))
            x, reason = j, "SL"
            break
        if not (fill_bar and j == e) and ((d == 1 and bh >= tp) or (d == -1 and bl <= tp)):
            exit_px = max(tp, bo) if d == 1 else min(tp, bo)
            x, reason = j, "TP"
            break
        best = max(best, hh[j]) if d == 1 else min(best, ll[j] + sj)
        if last[j] and par[j] >= 0:
            p = par[j]
            nb += 1
            ema = P["E"][100][p] if d * (best - entry) >= SWITCH * dist else P["E"][55][p]
            if d * (P["c"][p] - ema) < 0 and j + 1 < ns:
                x = j + 1
                exit_px = o[x] + (sp[x] if d == -1 else 0.0)
                reason = "TREND"
                break
            if nb >= ctx["hold"]:
                x, exit_px = j, c[j] + sj
                break
    if exit_px is None:
        x = ns - 1
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - P["comm"] / dist
    return {"d": d, "utc": int(S["utc"][e]), "r": float(r), "reason": reason, "risk": float(dist),
            "e": int(e), "x": int(x), "srv_in": int(S["t"][e]), "srv_out": int(S["t"][x]),
            "sp_in": float(sp[e]), "sp_out": float(sp[x]), "hold_h": float((S["t"][x] - S["t"][e]) / 3600),
            "entry": float(entry)}


def anchor_start(t, i, a0):
    for k in range(i, a0, -1):
        if t[k] - t[k - 1] > GAP:
            return k
    return a0


def finish(ctx, tr, i_sig, atr, kind):
    if tr is None:
        return None
    tr["dist_atr"] = tr["risk"] / atr
    tr["sig"] = int(i_sig)
    tr["kind"] = kind
    tr["p"] = period(tr["utc"])
    tr["rh"] = h.harsh(tr, ctx["S"])
    return tr


def base_trades(ctx):
    P, S = ctx["P"], ctx["S"]
    g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = ctx["comp"], ADX_LOW, DI_GAP, ADX_RISE
    sigs = [(i, d) for i, d in g.signals(P) if P["h4_side"][i] == d]
    out, free = [], 0
    W = ctx["comp"]
    for i, d in sigs:
        if i < free or i + 1 >= len(P["t"]):
            continue
        e = ctx["first"][i + 1]
        if e < 0 or S["utc"][e] < ctx["start"]:
            continue
        entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
        a0 = anchor_start(P["t"], i, i - W)
        anchor = (np.min(P["l"][a0:i + 1]) - BUF * P["atr"][i]) if d == 1 else (np.max(P["h"][a0:i + 1]) + BUF * P["atr"][i])
        dist = d * (entry - anchor)
        if dist > SMAX * P["atr"][i]:
            continue
        dist = max(dist, SMIN * P["atr"][i])
        tr = finish(ctx, walk(ctx, e, entry, d, dist), i, P["atr"][i], "B0")
        out.append(tr)
        free = ctx["par"][tr["x"]] + 1 + ctx["cool"]
    return out


def v1_trades(ctx):
    """Intrabar trigger: at every closed sub-bar of main bar i, the rule on the forming bar's provisional values."""
    P, S = ctx["P"], ctx["S"]
    W, a = ctx["comp"], 1.0 / 14
    adx, gap, trs, pdms, mdms, E = P["adx"], P["gap"], P["atr"], P["pdms"], P["mdms"], P["E"]
    ph, pl, pc = P["h"], P["l"], P["c"]
    out, free = [], 0
    n = len(P["t"])
    stats = {"early": 0, "at_close": 0, "faded": 0, "wide": 0}
    for i in range(400, n - 1):
        if i < free:
            continue
        side = int(P["h4_side"][i])
        if side == 0 or ctx["first"][i] < 0 or S["utc"][ctx["first"][i]] < ctx["start"]:
            continue
        k0 = i - W + int(np.argmin(adx[i - W:i]))
        if adx[k0] > ADX_LOW or abs(gap[k0]) > DI_GAP:
            continue
        q = i - 1
        hp, lp = -np.inf, np.inf
        fired = False
        for k in range(ctx["first"][i], ctx["lastsub"][i] + 1):
            hp, lp = max(hp, S["h"][k]), min(lp, S["l"][k])
            cp = S["c"][k]
            tr_ = max(hp - lp, abs(hp - pc[q]), abs(lp - pc[q]))
            up, dn = hp - ph[q], pl[q] - lp
            pdm = up if (up > dn and up > 0) else 0.0
            mdm = dn if (dn > up and dn > 0) else 0.0
            ts_ = trs[q] + a * (tr_ - trs[q])
            pd_ = pdms[q] + a * (pdm - pdms[q])
            md_ = mdms[q] + a * (mdm - mdms[q])
            pdi, mdi = 100 * pd_ / ts_, 100 * md_ / ts_
            dx = 100 * abs(pdi - mdi) / max(pdi + mdi, 1e-9)
            adx_p = adx[q] + a * (dx - adx[q])
            if not (adx_p > adx[q] and adx_p - adx[k0] <= ADX_RISE):
                continue
            ep = [E[m][q] + 2.0 / (m + 1) * (cp - E[m][q]) for m in (21, 55, 100, 200)]
            gp = pdi - mdi
            if side == 1 and not (gp > 0 and gp > gap[q] and cp > max(ep)):
                continue
            if side == -1 and not (gp < 0 and gp < gap[q] and cp < min(ep)):
                continue
            d = side
            at_close = (k == ctx["lastsub"][i])
            e = ctx["first"][i + 1] if at_close else k + 1
            if e < 0:
                break
            entry = S["o"][e] + (S["sp"][e] if d == 1 else 0.0)
            atr_p = ts_
            a0 = anchor_start(P["t"], i, i - W)
            if d == 1:
                anchor = (min(np.min(pl[a0:i]), lp) if a0 < i else lp) - BUF * atr_p
            else:
                anchor = (max(np.max(ph[a0:i]), hp) if a0 < i else hp) + BUF * atr_p
            dist = d * (entry - anchor)
            if dist > SMAX * atr_p:
                stats["wide"] += 1
                continue
            dist = max(dist, SMIN * atr_p)
            tr = finish(ctx, walk(ctx, e, entry, d, dist), i, atr_p, "V1")
            tr["at_close"] = at_close
            # did the main bar still meet the rule at its close?
            tr["faded"] = (not at_close) and not full_signal(P, i, W, d)
            stats["at_close" if at_close else "early"] += 1
            stats["faded"] += int(tr["faded"])
            tr["sub_k"] = int(k - ctx["first"][i])
            out.append(tr)
            free = ctx["par"][tr["x"]] + 1 + ctx["cool"]
            fired = True
            break
        if fired:
            continue
    return out, stats


def full_signal(P, i, W, d):
    adx, gap = P["adx"], P["gap"]
    k0 = i - W + int(np.argmin(adx[i - W:i]))
    if adx[k0] > ADX_LOW or abs(gap[k0]) > DI_GAP or not (adx[i] > adx[i - 1] and adx[i] - adx[k0] <= ADX_RISE):
        return False
    if d == 1:
        return gap[i] > 0 and gap[i] > gap[i - 1] and P["c"][i] > P["ehi"][i]
    return gap[i] < 0 and gap[i] < gap[i - 1] and P["c"][i] < P["elo"][i]


def v2_trades(ctx):
    """Stop order: armed after a main close inside a compression, level beyond the box and the EMA ribbon."""
    P, S = ctx["P"], ctx["S"]
    W = ctx["comp"]
    adx, gap, atr = P["adx"], P["gap"], P["atr"]
    out, free = [], 0
    n = len(P["t"])
    stats = {"placed": 0, "filled": 0, "fill_bar_sl": 0}
    for j in range(400, n - 1):
        if j < free:
            continue
        f, z = ctx["first"][j + 1], ctx["lastsub"][j + 1]
        if f < 0 or S["utc"][f] < ctx["start"]:
            continue
        d = int(P["h4_side"][j + 1])
        if d == 0:
            continue
        k0 = j - W + 1 + int(np.argmin(adx[j - W + 1:j + 1]))
        if adx[k0] > ADX_LOW or abs(gap[k0]) > DI_GAP or adx[j] - adx[k0] > ADX_RISE:
            continue
        a0 = anchor_start(P["t"], j, j - W)
        if d == 1:
            level = max(np.max(P["h"][a0:j + 1]), P["ehi"][j]) + BUF * atr[j]
            anchor = np.min(P["l"][a0:j + 1]) - BUF * atr[j]
        else:
            level = min(np.min(P["l"][a0:j + 1]), P["elo"][j]) - BUF * atr[j]
            anchor = np.max(P["h"][a0:j + 1]) + BUF * atr[j]
        if d * (level - anchor) > SMAX * atr[j]:
            continue
        stats["placed"] += 1
        for k in range(f, z + 1):
            sp = S["sp"][k]
            if d == 1 and S["h"][k] + sp >= level:
                fill = max(level, S["o"][k] + sp)
            elif d == -1 and S["l"][k] <= level:
                fill = min(level, S["o"][k])
            else:
                continue
            dist = d * (fill - anchor)
            if dist > SMAX * atr[j]:
                break
            dist = max(dist, SMIN * atr[j])
            tr = finish(ctx, walk(ctx, k, fill, d, dist, fill_bar=True), j, atr[j], "V2")
            tr["fill_bar_sl"] = tr["x"] == k and tr["reason"] == "SL"
            stats["filled"] += 1
            stats["fill_bar_sl"] += int(tr["fill_bar_sl"])
            out.append(tr)
            free = ctx["par"][tr["x"]] + 1 + ctx["cool"]
            break
    return out, stats


# ---------------------------------------------------------------------------
# random control: same count per period, same direction, same stop in ATR, entry after a main close
# ---------------------------------------------------------------------------
def random_job(arg):
    main, sub, rows, seed, runs = arg
    ctx = context(main, sub)
    P, S = ctx["P"], ctx["S"]
    rng = np.random.default_rng(seed)
    pools = {}
    for name in DECIDE:
        idx = np.nonzero(ctx["last"][:-1])[0]
        idx = idx[(ctx["par"][idx] > 400)]
        u = S["utc"][idx + 1]
        a, z = next((x[1], x[2]) for x in g.PERIODS if x[0] == name)
        pools[name] = idx[(u >= max(a, ctx["start"])) & (u < z)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            k = int(rng.choice(pools[t["p"]]))
            p = ctx["par"][k]
            e = k + 1
            entry = S["o"][e] + (S["sp"][e] if t["d"] == 1 else 0.0)
            tr = walk(ctx, e, entry, t["d"], t["dist_atr"] * P["atr"][p])
            rs.append(h.harsh(tr, S))
        means.append(float(np.mean(rs)))
    return means


def p_random(main, sub, trs):
    dec = [t for t in trs if t["p"] in DECIDE]
    if len(dec) < 10:
        return float("nan"), float("nan")
    real = float(np.mean([t["rh"] for t in dec]))
    lite = [{"p": t["p"], "d": t["d"], "dist_atr": t["dist_atr"]} for t in dec]
    jobs = [(main, sub, lite, 7300 + k, RUNS // 10) for k in range(10)]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(random_job, jobs) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------
def summary(trs, d):
    x = [t for t in trs if t["d"] == d]
    per = {k: g.stats([t["rh"] for t in x if t["p"] == k]) for k in KEYS}
    dec = [t for t in x if t["p"] in DECIDE]
    rh = [t["rh"] for t in dec]
    return {"per": per, "n": len(dec), "exp": float(np.mean(rh)) if rh else 0.0, "total": float(np.sum(rh)) if rh else 0.0,
            "raw": float(np.mean([t["r"] for t in dec])) if dec else 0.0,
            "dd": h.dd_p90([{"utc": t["utc"], "r": t["rh"]} for t in dec], 0.015) if len(dec) >= 20 else float("nan"),
            "stop_atr": float(np.median([t["dist_atr"] for t in dec])) if dec else 0.0,
            "trades": x}


def earliness(v, base, ctx, d):
    """Pairs a V trade with the B0 trade of the same burst (B0 signal within the next W main bars)."""
    W = ctx["comp"]
    b = [t for t in base if t["d"] == d]
    mins, gain = [], []
    for t in v:
        if t["d"] != d or t["p"] not in DECIDE:
            continue
        pv = ctx["par"][t["e"]]
        m = [x for x in b if pv - 1 <= x["sig"] <= pv + W]
        if not m:
            continue
        x = m[0]
        mins.append((x["srv_in"] - t["srv_in"]) / 60)
        gain.append(d * (x["entry"] - t["entry"]) / x["risk"])
    return (float(np.median(mins)) if mins else float("nan"), float(np.median(gain)) if gain else float("nan"), len(mins))


def verdict(v, b, p):
    per = v["per"]
    checks = [v["exp"] >= b["exp"], v["total"] >= b["total"], all(per[k]["n"] and per[k]["exp"] > 0 for k in DECIDE),
              (v["dd"] <= b["dd"] + 0.02) if not np.isnan(v["dd"]) else False, (p < 0.05 / N_TESTS) if not np.isnan(p) else False]
    return checks


def examples(trs):
    out = []
    for name, d, a, z in EXAMPLES:
        a = datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        z = datetime.fromisoformat(z).replace(tzinfo=timezone.utc).timestamp() - 7 * 3600
        hit = [t for t in trs if t["d"] == d and a <= t["utc"] <= z]
        if hit:
            t = hit[0]
            vn = datetime.fromtimestamp(t["utc"] + 7 * 3600, timezone.utc)
            out.append(f"{name}: vào {vn:%d/%m %H:%M} VN, {t['rh']:+.2f}R")
        else:
            out.append(f"{name}: không vào")
    return out


def cell(s):
    return f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"


def main():
    lines = ["# G73: Vào lệnh sớm cho S07 — kết quả", "",
             "Kế hoạch: `plans/2026-10-10-g73-early-entry.md`. Số liệu: chi phí khắt khe G68, R/lệnh; "
             "\"Gộp\" = train + validate + test. DD p90 ở rủi ro 1,5%/lệnh, cửa sổ 1 năm.", ""]
    dump = {}
    for main_tf, sub in (("M30", "M15"), ("H1", "M15"), ("M15", "M5"), ("M30", "M5")):
        ctx = context(main_tf, sub)
        primary = not (main_tf == "M30" and sub == "M5")
        base = base_trades(ctx)
        v1, s1 = v1_trades(ctx)
        v2, s2 = v2_trades(ctx)
        start = datetime.fromtimestamp(ctx["start"], timezone.utc)
        lines += [f"## Khung {main_tf}, nến nhỏ {sub}" + ("" if primary else " (kiểm tra M5, chỉ báo cáo)"), "",
                  f"Nến nhỏ có từ {start:%d/%m/%Y}; nến nhỏ khớp nến chính (giá đóng): {ctx['agree']:.1%}. "
                  f"V1: {s1['early']} lệnh vào giữa nến, {s1['at_close']} lúc đóng nến, {s1['faded']} tín hiệu giữa nến mất khi nến đóng, "
                  f"{s1['wide']} lần bỏ vì SL > 4 ATR. V2: {s2['placed']} lần đặt lệnh chờ, {s2['filled']} lần khớp, "
                  f"{s2['fill_bar_sl']} lần chạm SL ngay nến khớp.", "",
                  "| Chiều | Cách | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | R/lệnh chi phí thường | DD p90 | SL (ATR) | Ngẫu nhiên (TB / p) | Sớm hơn B0 (phút, R giá vào, cặp) | Đạt |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d, dn in ((1, "Mua"), (-1, "Bán")):
            sb = summary(base, d)
            res = {"B0": sb}
            for name, trs in (("V1", v1), ("V2", v2)):
                res[name] = summary(trs, d)
            for name in ("B0", "V1", "V2"):
                s = res[name]
                if primary:
                    rm, p = p_random(main_tf, sub, s["trades"])
                else:
                    rm, p = float("nan"), float("nan")
                s["p"] = p
                ok = ""
                early = ""
                if name != "B0":
                    c = verdict(s, sb, p) if primary else None
                    ok = ("**ĐẠT**" if all(c) else "không (" + ", ".join(str(k + 1) for k, x in enumerate(c) if not x) + ")") if c else "—"
                    m, gn, npair = earliness(s["trades"], base, ctx, d)
                    early = f"{m:.0f} / {gn:+.2f} / {npair}"
                pr = s["per"]
                dd_txt = "—" if np.isnan(s["dd"]) else f"{s['dd']:.0%}"
                lines.append(f"| {dn} | {name} | {cell(pr['train'])} | {cell(pr['validate'])} | {cell(pr['test'])} | {cell(pr['examples'])} | "
                             f"{s['n']} | {s['exp']:+.3f} | {s['total']:+.1f} | {s['raw']:+.3f} | "
                             f"{dd_txt} | {s['stop_atr']:.2f} | "
                             f"{'—' if np.isnan(p) else f'{rm:+.3f} / {p:.3f}'} | {early} | {ok} |")
                dump[f"{main_tf}/{sub}/{dn}/{name}"] = {k: v for k, v in s.items() if k != "trades"}
        lines.append("")
        for name, trs in (("B0", base), ("V1", v1), ("V2", v2)):
            lines.append(f"- Ví dụ {name}: " + "; ".join(examples(trs)))
        lines.append("")
    lines += ["Cột Đạt: số trong ngoặc là tiêu chí không đạt (1 R/lệnh ≥ B0, 2 tổng R ≥ B0, 3 dương cả train/validate/test, "
              "4 DD p90 ≤ B0 + 2 điểm %, 5 thắng ngẫu nhiên p < 0,05/12).", ""]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    g.OUT.mkdir(exist_ok=True)
    (g.OUT / "g73_early.json").write_text(json.dumps(dump, indent=1, default=float), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
