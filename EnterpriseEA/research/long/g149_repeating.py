"""G149: repeating price behaviour (Q1-Q8) and six order cells (K1-K4 scalp, W1-W2 swing) on gold M30 from 05/2018.
Plan: docs/superpowers/plans/2026-10-22-g149-repeating-behaviour.md.

Usage: g149_repeating.py <data dir> <out.json>
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g137_patterns as gp  # noqa: E402
import g147_risk_map as rm  # noqa: E402
import g148_layered_risk_map as lm  # noqa: E402

H = 3600
START = rm.START
PVAL, RUNS = 0.008, 200
PNAMES = ("chọn", "validate", "test", "sau")


def stat(x):
    x = np.asarray(list(x), dtype=float)
    return {"n": int(len(x)), "mean": round(float(x.mean()), 3), "total": round(float(x.sum()), 1)} if len(x) else {"n": 0}


class Ctx:
    def __init__(self, D, B, C):
        self.D, self.B, self.C = D, B, C
        t = D["t"]
        self.day = t // 86400
        self.tod = t % 86400
        ends = np.r_[np.nonzero(np.diff(self.day))[0], len(t) - 1]
        starts = np.r_[0, ends[:-1] + 1]
        self.days = [(int(self.day[a]), int(a), int(z)) for a, z in zip(starts, ends)]
        self.pos = {int(x): k for k, x in enumerate(t)}

    def bar_at(self, dk, sec):
        return self.pos.get(dk * 86400 + sec)

    def exit_idx(self, dk, z):
        k = self.bar_at(dk, 22 * H)                    # close of the 22:00 bar = 22:30
        return k if k is not None else z


def make(cx, e, d, entry, sl, tp, x_idx, meta):
    D = cx.D
    if e >= len(D["c"]) or x_idx < e:
        return None
    dist = d * (entry - sl)
    if dist <= 0:
        return None
    tp_ = tp if tp is not None else entry + d * 1e6
    if d * (tp_ - entry) <= 0:
        return None
    t = gp.run_trade(D, e, d, entry, sl, tp_, x_idx - e + 1)
    if t is None:
        return None
    srv = int(D["t"][e])
    tp_r = d * (tp_ - entry) / dist - D["comm"] / dist
    A = D["atr"][e - 1]
    t.update(meta, p=rm.period(srv), srv=srv, hour=int(D["hour"][e - 1]), mon=int(D["mon"][e]),
             hit_tp=tp is not None and abs(t["r"] - tp_r) < 1e-9, k_sl=dist / A,
             k_tp=(d * (tp_ - entry) / A) if tp is not None else None, hold=x_idx - e + 1,
             near200=abs(D["c"][e - 1] - cx.C["dE200"][e - 1]) <= cx.C["dA"][e - 1], atr_low=D["atrr"][e - 1] < 0.8)
    return t


# ------------------------------------------------------------------------------------------------ cells
def k1(cx, opt):
    D, out = cx.D, []
    c, o, sp, a = D["c"], D["o"], D["sp"], D["atr"]
    for dk, s, z in cx.days:
        if int(D["t"][s]) < START:
            continue
        pdh, pdl = D["pdh"][s], D["pdl"][s]
        if not np.isfinite(pdh):
            continue
        xi = cx.exit_idx(dk, z)
        done = {1: False, -1: False}
        for i in range(s, min(z, xi)):
            hr = D["hour"][i]
            if not 1 <= hr <= 21:
                continue
            th, tl = cx.B["today_h"][i], cx.B["today_l"][i]
            for d in (1, -1):
                if done[d]:
                    continue
                if (d == 1 and tl < pdl and c[i] > pdl) or (d == -1 and th > pdh and c[i] < pdh):
                    done[d] = True
                    e, A = i + 1, a[i]
                    entry = o[e] + (sp[e] if d == 1 else 0.0)
                    sl = tl - 0.1 * A if d == 1 else th + 0.1 * A
                    if not 0.3 * A <= d * (entry - sl) <= 3 * A:
                        continue
                    tp = (pdh + pdl) / 2 if opt == 0 else (pdh if d == 1 else pdl)
                    t = make(cx, e, d, entry, sl, tp, xi, {})
                    if t:
                        out.append(t)
    return out


def k2(cx, opt):
    D, out = cx.D, []
    c, o, h, l, sp, a = D["c"], D["o"], D["h"], D["l"], D["sp"], D["atr"]
    for dk, s, z in cx.days:
        if int(D["t"][s]) < START:
            continue
        k9 = cx.bar_at(dk, 9 * H)
        if k9 is None:
            continue
        ah, al = cx.B["asia_h"][k9], cx.B["asia_l"][k9]
        if not np.isfinite(ah) or ah - al < 0.5 * a[k9]:
            continue
        xi = cx.exit_idx(dk, z)
        lo = hi = None
        done = {1: False, -1: False}
        for i in range(k9, min(z, xi)):
            lo = l[i] if lo is None else min(lo, l[i])
            hi = h[i] if hi is None else max(hi, h[i])
            for d in (1, -1):
                if done[d]:
                    continue
                if (d == 1 and lo < al and c[i] > al) or (d == -1 and hi > ah and c[i] < ah):
                    done[d] = True
                    e, A = i + 1, a[i]
                    entry = o[e] + (sp[e] if d == 1 else 0.0)
                    sl = lo - 0.1 * A if d == 1 else hi + 0.1 * A
                    if not 0.3 * A <= d * (entry - sl) <= 3 * A:
                        continue
                    tp = (ah + al) / 2 if opt == 0 else (ah if d == 1 else al)
                    t = make(cx, e, d, entry, sl, tp, xi, {})
                    if t:
                        out.append(t)
    return out


def k3(cx, opt):
    D, out = cx.D, []
    h, l, o, sp, a = D["h"], D["l"], D["o"], D["sp"], D["atr"]
    f = (0.382, 0.5)[opt]
    n = len(h)
    busy = {1: -1, -1: -1}
    for i in range(300, n - 2):
        if int(D["t"][i]) < START:
            continue
        A = a[i]
        for d in (1, -1):
            if i <= busy[d]:
                continue
            win_h, win_l = h[i - 19:i + 1], l[i - 19:i + 1]
            if d == 1:
                top, bot = win_h.max(), win_l.min()
                if not (h[i] == top and top - bot >= 3 * A and np.argmin(win_l) < 19):
                    continue
                lim, sl, tp = top - f * (top - bot), top - 0.786 * (top - bot), top
            else:
                top, bot = win_l.min(), win_h.max()
                if not (l[i] == top and bot - top >= 3 * A and np.argmax(win_h) < 19):
                    continue
                lim, sl, tp = top + f * (bot - top), top + 0.786 * (bot - top), top
            if not 0.3 * A <= abs(lim - sl) <= 4 * A:
                continue
            for j in range(i + 1, min(i + 17, n - 1)):
                beyond = (h[j] >= tp) if d == 1 else (l[j] + sp[j] <= tp)
                fill = (l[j] + sp[j] <= lim) if d == 1 else (h[j] >= lim)
                if fill and beyond:
                    busy[d] = j; break                              # order inside the bar unknown: cancel
                if beyond:
                    busy[d] = j; break                              # new extreme before the fill: cancel
                if fill:
                    entry = min(lim, o[j] + sp[j]) if d == 1 else max(lim, o[j])
                    t = make(cx, j, d, entry, sl, tp, min(j + 47, n - 1), {})
                    if t:
                        out.append(t); busy[d] = t["x"]
                    else:
                        busy[d] = j
                    break
            else:
                busy[d] = min(i + 16, n - 1)
    return out


def k4(cx, opt):
    D, out = cx.D, []
    c, o, sp, a = D["c"], D["o"], D["sp"], D["atr"]
    for dk, s, z in cx.days:
        if int(D["t"][s]) < START:
            continue
        xi = cx.exit_idx(dk, z)
        done = {1: False, -1: False}                                 # side of VWAP
        for i in range(s, min(z, xi)):
            if not 10 <= D["hour"][i] <= 20:
                continue
            A = a[i]
            dv = (c[i] - cx.B["vwap"][i]) / A
            side = 1 if dv >= 1.5 else (-1 if dv <= -1.5 else 0)
            if side == 0 or done[side]:
                continue
            done[side] = True
            e = i + 1
            if opt == 0:                                             # fade back to VWAP
                d = -side
                entry = o[e] + (sp[e] if d == 1 else 0.0)
                tp, sl = cx.B["vwap"][i], entry - d * 1.0 * A
            else:                                                    # follow
                d = side
                entry = o[e] + (sp[e] if d == 1 else 0.0)
                tp, sl = entry + d * 1.5 * A, entry - d * 1.0 * A
            t = make(cx, e, d, entry, sl, tp, xi, {})
            if t:
                out.append(t)
    return out


def weeks(cx):
    D = cx.D
    wk = (cx.day + 3) // 7
    out = defaultdict(list)
    for dk, s, z in cx.days:
        out[int((dk + 3) // 7)].append((dk, s, z))
    return out


def friday_exit(cx, wdays):
    dk, s, z = wdays[-1]
    if (dk + 3) % 7 != 4:
        return None
    k = cx.bar_at(dk, 21 * H)
    return k if k is not None else z


def w1(cx, opt):
    D, out = cx.D, []
    h, l, o, sp = D["h"], D["l"], D["o"], D["sp"]
    for w, wd in sorted(weeks(cx).items()):
        if int(D["t"][wd[0][1]]) < START:
            continue
        xi = friday_exit(cx, wd)
        if xi is None:
            continue
        s0 = wd[0][1]
        pwh, pwl = cx.C["pwH"][s0], cx.C["pwL"][s0]
        if not np.isfinite(pwh):
            continue
        mid, rng = (pwh + pwl) / 2, pwh - pwl
        for d in (1, -1):
            for dk, s, z in wd:
                if (dk + 3) % 7 > 3:
                    break
                hit = None
                for j in range(s, z + 1):
                    if (d == 1 and h[j] + sp[j] >= pwh) or (d == -1 and l[j] <= pwl):
                        hit = j; break
                if hit is not None:
                    if hit == s0 and ((d == 1 and o[hit] > pwh) or (d == -1 and o[hit] < pwl)):
                        break                                        # opened beyond: no breakout order to fill
                    entry = max(pwh, o[hit] + sp[hit]) if d == 1 else min(pwl, o[hit])
                    tp = None if opt == 0 else (pwh + rng if d == 1 else pwl - rng)
                    t = make(cx, hit, d, entry, mid, tp, xi, {})
                    if t:
                        out.append(t)
                    break
    return out


def w2(cx, opt):
    D, out = cx.D, []
    h, l, c, o, sp = D["h"], D["l"], D["c"], D["o"], D["sp"]
    for w, wd in sorted(weeks(cx).items()):
        if int(D["t"][wd[0][1]]) < START:
            continue
        xi = friday_exit(cx, wd)
        if xi is None:
            continue
        s0 = wd[0][1]
        pwh, pwl = cx.C["pwH"][s0], cx.C["pwL"][s0]
        if not np.isfinite(pwh):
            continue
        mid = (pwh + pwl) / 2
        for d in (-1, 1):                                            # -1: sweep of the high then sell; +1: sweep of the low then buy
            wh, wl = -1e18, 1e18
            for n_, (dk, s, z) in enumerate(wd[:-1]):
                wh, wl = max(wh, h[s:z + 1].max()), min(wl, l[s:z + 1].min())
                dA = cx.C["dA"][s]
                if not np.isfinite(dA):
                    continue
                if d == -1:
                    ok = wh > pwh and wh - pwh <= 0.5 * dA and c[z] < pwh
                    sl, tp = wh + 0.1 * dA, (mid if opt == 0 else pwl)
                else:
                    ok = wl < pwl and pwl - wl <= 0.5 * dA and c[z] > pwl
                    sl, tp = wl - 0.1 * dA, (mid if opt == 0 else pwh)
                if ok:
                    e = wd[n_ + 1][1]
                    entry = o[e] + (sp[e] if d == 1 else 0.0)
                    t = make(cx, e, d, entry, sl, tp, xi, {})
                    if t:
                        out.append(t)
                    break
    return out


CELLS = {"K1 quét đỉnh/đáy hôm qua rồi quay về": (k1, ("TP giữa biên hôm qua", "TP đỉnh/đáy hôm qua"), 40),
         "K2 phá biên phiên Á rồi quay về": (k2, ("TP giữa biên Á", "TP biên Á đối diện"), 40),
         "K3 hồi trong nhịp mạnh (limit)": (k3, ("f 0,382", "f 0,5"), 40),
         "K4 giá xa VWAP ngày": (k4, ("ngược về VWAP", "theo hướng"), 40),
         "W1 phá đỉnh/đáy tuần trước": (w1, ("không TP", "TP 1 × biên tuần"), 20),
         "W2 quét đỉnh/đáy tuần trước rồi quay về": (w2, ("TP giữa biên tuần trước", "TP biên đối diện"), 20)}


def evaluate(cx, rows, min_n):
    D = cx.D
    vt = [t for t in rows if t["p"] in ("validate", "test")]
    res = {"theo kỳ": {p: stat(t["rh"] for t in rows if t["p"] == p) for p in PNAMES},
           "tỷ lệ thắng (val+test)": round(float(np.mean([t["rh"] > 0 for t in vt])), 3) if vt else None,
           "tỷ lệ chạm TP (val+test)": round(float(np.mean([t["hit_tp"] for t in vt])), 3) if vt else None,
           "lãi TB / lỗ TB (val+test)": [round(float(np.mean([t["rh"] for t in vt if t["rh"] > 0] or [0])), 3),
                                         round(float(np.mean([t["rh"] for t in vt if t["rh"] <= 0] or [0])), 3)],
           "mua (val+test)": stat(t["rh"] for t in vt if t["d"] == 1), "bán (val+test)": stat(t["rh"] for t in vt if t["d"] == -1),
           "tháng không tăng": stat(t["rh"] for t in vt if D["down_month"].get(t["mon"])),
           "phí×1,5": stat(t["rh15"] for t in vt), "bỏ 5 lệnh lớn nhất": stat(sorted(t["rh"] for t in vt)[:-5]),
           "bỏ vùng sát EMA200 D1": stat(t["rh"] for t in vt if not t["near200"]),
           "bỏ ATR thấp": stat(t["rh"] for t in vt if not t["atr_low"]),
           "theo năm": {str(y): stat(t["rh"] for t in rows if g.ts(y, 1, 1) <= t["srv"] < g.ts(y + 1, 1, 1)) for y in range(2018, 2027)}}
    mons = sorted({int(m) for m in D["mon"][(D["t"] >= g.ts(2022, 1, 1)) & (D["t"] < g.ts(2026, 7, 1))]})
    ms = defaultdict(float)
    for t in vt:
        ms[t["mon"]] += t["rh"]
    seq = [ms[m] for m in mons]
    res["cửa sổ 6 tháng tệ nhất (R)"] = round(float(min(sum(seq[j:j + 6]) for j in range(len(seq) - 5))), 1) if len(seq) > 6 else None
    # random control: same period, direction, server hour; random bar; same SL / TP in ATR and same hold
    pool = defaultdict(list)
    for i in range(300, len(D["c"]) - 50):
        p = rm.period(int(D["t"][i]))
        if p in ("validate", "test"):
            pool[(p, int(D["hour"][i]))].append(i)
    actual = float(np.mean([t["rh"] for t in vt])) if vt else -9
    rng = random.Random(149)
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in vt:
            cand = pool.get((t["p"], t["hour"])) or pool[(t["p"], 12)]
            for _ in range(20):
                i = rng.choice(cand)
                e, A, d = i + 1, D["atr"][i], t["d"]
                entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
                tp = entry + d * t["k_tp"] * A if t["k_tp"] is not None else entry + d * 1e6
                r = gp.run_trade(D, e, d, entry, entry - d * t["k_sl"] * A, tp, t["hold"])
                if r:
                    u.append(r["rh"]); break
        hits += float(np.mean(u)) >= actual
    res["p ngẫu nhiên"] = (hits + 1) / (RUNS + 1)
    per = res["theo kỳ"]
    ok = (all(per[p]["n"] >= min_n and per[p]["mean"] > 0 for p in ("validate", "test"))
          and res["mua (val+test)"].get("mean", -1) > 0 and res["bán (val+test)"].get("mean", -1) > 0
          and res["tháng không tăng"].get("mean", -1) > 0 and res["p ngẫu nhiên"] <= PVAL
          and res["phí×1,5"].get("mean", -1) > 0 and res["bỏ 5 lệnh lớn nhất"].get("mean", -1) > 0
          and (res["cửa sổ 6 tháng tệ nhất (R)"] or -99) >= -15)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    return res


# ------------------------------------------------------------------------------------------------ part 1
def regularities(cx):
    D, B = cx.D, cx.B
    h, l, c, a = D["h"], D["l"], D["c"], D["atr"]
    by_year = defaultdict(lambda: defaultdict(list))
    for dk, s, z in cx.days:
        if int(D["t"][s]) < START:
            continue
        y = int(np.datetime64(dk, "D").astype("datetime64[Y]").astype(int) + 1970)
        pdh, pdl = D["pdh"][s], D["pdl"][s]
        if not np.isfinite(pdh):
            continue
        dh, dl = h[s:z + 1].max(), l[s:z + 1].min()
        R = by_year[y]
        R["Q1 chạm đỉnh hôm qua"].append(dh >= pdh); R["Q1 chạm đáy hôm qua"].append(dl <= pdl)
        R["Q1 chạm cả hai"].append(dh >= pdh and dl <= pdl)
        if dh > pdh:
            R["Q2 thủng đỉnh hôm qua → đóng lại trong biên"].append(c[z] < pdh)
        if dl < pdl:
            R["Q2 thủng đáy hôm qua → đóng lại trong biên"].append(c[z] > pdl)
        k9 = cx.bar_at(dk, 9 * H)
        xi = cx.exit_idx(dk, z)
        if k9 is not None and np.isfinite(B["asia_h"][k9]):
            ah, al = B["asia_h"][k9], B["asia_l"][k9]
            after_h, after_l = h[k9:xi + 1], l[k9:xi + 1]
            brk = after_h.max() > ah or after_l.min() < al
            R["Q3 phá biên Á sau 09:00"].append(brk)
            if after_h.max() > ah:
                j = k9 + int(np.argmax(after_h > ah))
                R["Q3 phá đỉnh Á → quay lại trong biên"].append(bool((c[j:xi + 1] < ah).any()))
            if after_l.min() < al:
                j = k9 + int(np.argmax(after_l < al))
                R["Q3 phá đáy Á → quay lại trong biên"].append(bool((c[j:xi + 1] > al).any()))
        for i in range(s, min(z, xi)):
            if not 10 <= D["hour"][i] <= 20:
                continue
            dv = (c[i] - B["vwap"][i]) / a[i]
            if abs(dv) >= 1.5:
                side, vw, A = np.sign(dv), B["vwap"][i], a[i]
                touch = ext = None
                for j in range(i + 1, xi + 1):
                    if touch is None and l[j] <= vw <= h[j]:
                        touch = j
                    if ext is None and ((side > 0 and h[j] >= c[i] + A) or (side < 0 and l[j] <= c[i] - A)):
                        ext = j
                R["Q4 xa VWAP ≥1,5 ATR → chạm lại VWAP trước"].append(touch is not None and (ext is None or touch < ext))
                R["Q4 xa VWAP ≥1,5 ATR → đi thêm 1 ATR trước"].append(ext is not None and (touch is None or ext < touch))
                break
    rng = random.Random(1491)
    n = len(c)
    for _ in range(40000):
        i = rng.randrange(300, n - 60)
        if int(D["t"][i]) < START:
            continue
        y = int(np.datetime64(int(D["t"][i]) // 86400, "D").astype("datetime64[Y]").astype(int) + 1970)
        d, A, e = rng.choice((1, -1)), a[i], c[i]
        got1 = False
        for j in range(i + 1, i + 49):
            if not got1:
                if (d == 1 and h[j] >= e + A) or (d == -1 and l[j] <= e - A):
                    got1 = True
                elif (d == 1 and l[j] <= e - A) or (d == -1 and h[j] >= e + A):
                    break
            if got1:
                if (d == 1 and l[j] <= e) or (d == -1 and h[j] >= e):
                    by_year[y]["Q6 đã +1 ATR → tới +2 ATR trước khi về giá vào"].append(False); break
                if (d == 1 and h[j] >= e + 2 * A) or (d == -1 and l[j] <= e - 2 * A):
                    by_year[y]["Q6 đã +1 ATR → tới +2 ATR trước khi về giá vào"].append(True); break
    out = {}
    keys = sorted({k for y in by_year for k in by_year[y]})
    for k in keys:
        out[k] = {str(y): [round(float(np.mean(v)), 3), len(v)] for y, R in sorted(by_year.items()) for kk, v in R.items() if kk == k}
    # Q7 hour of the day's high and low
    hh, hl = defaultdict(int), defaultdict(int)
    for dk, s, z in cx.days:
        if int(D["t"][s]) < START or z - s < 30:
            continue
        hh[int(D["hour"][s + int(np.argmax(h[s:z + 1]))])] += 1
        hl[int(D["hour"][s + int(np.argmin(l[s:z + 1]))])] += 1
    tot = sum(hh.values())
    out["Q7 giờ hình thành đỉnh ngày (%)"] = {k: round(100 * v / tot, 1) for k, v in sorted(hh.items())}
    out["Q7 giờ hình thành đáy ngày (%)"] = {k: round(100 * v / tot, 1) for k, v in sorted(hl.items())}
    return out


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    cx = Ctx(D, lm.bar_context(D), lm.daily_context(D))
    res = {"phần 1 quy luật": regularities(cx)}
    print("part 1 done", flush=True)
    res["phần 2 ô lệnh"] = {}
    for name, (fn, opts, min_n) in CELLS.items():
        sel = {}
        rows_by = {}
        for k, oname in enumerate(opts):
            rows = [t for t in fn(cx, k) if t["p"]]
            rows_by[k] = rows
            s_ = [t["rh"] for t in rows if t["p"] == "chọn"]
            sel[oname] = [round(float(np.mean(s_)), 3) if s_ else None, len(s_)]
        best = max(range(len(opts)), key=lambda k: sel[opts[k]][0] if sel[opts[k]][0] is not None else -9)
        r = evaluate(cx, rows_by[best], min_n)
        r["lựa chọn trên kỳ chọn"] = sel
        r["chọn"] = opts[best]
        res["phần 2 ô lệnh"][name] = r
        print(name, r["chọn"], r["theo kỳ"], r["p ngẫu nhiên"], r["kết luận"], flush=True)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
