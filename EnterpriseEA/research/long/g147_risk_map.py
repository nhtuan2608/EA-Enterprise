"""G147: risk map over 21 factors on an every-bar M30 trade universe; stability-first avoid / favour states; combined system.
Plan: docs/superpowers/plans/2026-10-22-g147-risk-map.md.

Universe starts 2018-05-01 (not 2018-03-19): the H4 EMA200 and ATR100 need ~6 weeks of real intraday bars after the D1-only
history ends (decided before running, data hygiene).
Usage: g147_risk_map.py <data dir> <out.json>
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
import g139_hybrid as hy  # noqa: E402

START = g.ts(2018, 5, 1)
PER = [("chọn", START, g.ts(2022, 1, 1)), ("validate", g.ts(2022, 1, 1), g.ts(2024, 1, 1)),
       ("test", g.ts(2024, 1, 1), g.ts(2026, 7, 1)), ("sau", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
SEL_YEARS = (2018, 2019, 2020, 2021)
MIN_SHARE, MIN_DELTA = 0.05, 0.03
RUNS = 200
ROUND_B = len(sys.argv) > 3 and sys.argv[3] == "b"
PVAL = 0.005 if ROUND_B else 0.01


def period(srv):
    for n, a, z in PER:
        if a <= srv < z:
            return n
    return None


def factors(D, i, d):
    c, o, h, l, a = D["c"], D["o"], D["h"], D["l"], D["atr"]
    E, adx = D["E"], D["adx"]
    f = {}
    ordr = 1 if E[21][i] > E[55][i] > E[100][i] else (-1 if E[21][i] < E[55][i] < E[100][i] else 0)
    f["F1 EMA21/55/100"] = "cùng" if ordr == d else ("ngược" if ordr == -d else "lẫn")
    f["F2 giá vs EMA200"] = "cùng" if d * (c[i] - E[200][i]) > 0 else "ngược"
    sl = (E[200][i] - E[200][i - 48]) / a[i]
    f["F3 dốc EMA200"] = "phẳng" if abs(sl) < 0.5 else ("cùng" if np.sign(sl) == d else "ngược")
    f["F4 EMA200 H4"] = "cùng" if D["h4_side"][i] == d else "ngược"
    f["F5 D1 SMA50/200"] = "cùng" if D["d1"][i] == d else ("ngược" if D["d1"][i] == -d else "chưa rõ")
    f["F6 ADX"] = "<20" if adx[i] < 20 else ("20–30" if adx[i] <= 30 else ">30")
    f["F7 ADX 3 nến"] = "tăng" if adx[i] > adx[i - 3] else "giảm"
    f["F8 DI"] = "cùng" if d * (D["pdi"][i] - D["mdi"][i]) > 0 else "ngược"
    f["F9 MACD hist"] = "cùng" if d * D["hist"][i] > 0 else "ngược"
    f["F10 MACD hist đổi"] = "mạnh lên" if d * (D["hist"][i] - D["hist"][i - 1]) > 0 else "yếu đi"
    r = D["rsi"][i] if d == 1 else 100 - D["rsi"][i]
    f["F11 RSI theo chiều"] = ">70" if r > 70 else ("55–70" if r > 55 else ("45–55" if r >= 45 else ("30–45" if r >= 30 else "<30")))
    rk = D["bwrank"][i]
    f["F12 độ rộng Bollinger"] = "hẹp" if rk <= 0.2 else ("rộng" if rk >= 0.8 else "thường")
    ar = D["atrr"][i]
    f["F13 ATR/TB100"] = "thấp" if ar < 0.8 else ("cao" if ar > 1.25 else "thường")
    hr = D["hour"][i]
    f["F14 phiên"] = "Á" if 1 <= hr <= 9 else ("London" if hr <= 14 else ("New York" if hr <= 19 else "tối"))
    f["F15 thứ"] = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")[int(D["wd"][i])]
    PH, PL = D["pdh"][i], D["pdl"][i]
    if d == 1:
        f["F16 cản phía trước"] = "đã vượt" if c[i] > PH else ("sát ≤0,5ATR" if PH - c[i] <= 0.5 * a[i] else "xa")
        f["F17 đỡ phía sau"] = "sát ≤0,5ATR" if c[i] - PL <= 0.5 * a[i] else "xa"
    else:
        f["F16 cản phía trước"] = "đã vượt" if c[i] < PL else ("sát ≤0,5ATR" if c[i] - PL <= 0.5 * a[i] else "xa")
        f["F17 đỡ phía sau"] = "sát ≤0,5ATR" if PH - c[i] <= 0.5 * a[i] else "xa"
    mv = d * (c[i] - c[i - 20]) / a[i]
    f["F18 đi 20 nến"] = "cùng >2ATR" if mv > 2 else ("cùng ≤2ATR" if mv >= 0 else "ngược")
    b = c[i] - o[i]
    f["F19 nến tín hiệu"] = ("thân lớn cùng" if np.sign(b) == d else "thân lớn ngược") if abs(b) >= 0.6 * a[i] else "nhỏ"
    vr = D["v"][i] / D["vavg"][i] if D["vavg"][i] > 0 else 1.0
    f["F20 tick volume"] = "cao" if vr >= 1.5 else ("thấp" if vr <= 0.7 else "thường")
    hi20, lo20 = h[i - 19:i + 1].max(), l[i - 19:i + 1].min()
    pos = (c[i] - lo20) / max(hi20 - lo20, 1e-9)
    pos = pos if d == 1 else 1 - pos
    f["F21 vị trí 20 nến"] = "sát cực theo chiều" if pos >= 0.8 else ("sát cực ngược" if pos <= 0.2 else "giữa")
    return f


def prepare(D):
    hy.prepare(D)
    c, t = D["c"], D["t"]
    m = g.ema(c, 12) - g.ema(c, 26)
    D["hist"] = m - g.ema(m, 9)
    n = len(c)
    W = np.lib.stride_tricks.sliding_window_view(D["bw"], 120)
    rk = np.full(n, np.nan)
    rk[119:] = (W <= W[:, -1:]).mean(1)
    D["bwrank"] = rk
    a = D["atr"]
    cs = np.concatenate([[0.0], np.cumsum(a)])
    am = np.full(n, np.nan)
    am[100:] = (cs[100:n] - cs[0:n - 100]) / 100
    D["atrr"] = a / am
    day = t // 86400
    D["wd"] = (day + 3) % 7
    ends = np.r_[np.nonzero(np.diff(day))[0], n - 1]
    starts = np.r_[0, ends[:-1] + 1]
    dh = {int(day[s]): D["h"][s:e + 1].max() for s, e in zip(starts, ends)}
    dl = {int(day[s]): D["l"][s:e + 1].min() for s, e in zip(starts, ends)}
    days = sorted(dh)
    prev = {days[k]: days[k - 1] for k in range(1, len(days))}
    D["pdh"] = np.array([dh.get(prev.get(int(x), -1), np.nan) for x in day])
    D["pdl"] = np.array([dl.get(prev.get(int(x), -1), np.nan) for x in day])
    # month "not up": month-end close <= previous month-end close (server time)
    mon = (t // 86400).astype("datetime64[D]").astype("datetime64[M]").astype(int)
    mend = {}
    for k in range(n):
        mend[int(mon[k])] = c[k]
    D["mon"] = mon
    D["down_month"] = {mm: (mm - 1 in mend and mend[mm] <= mend[mm - 1]) for mm in mend}
    return D


def universe(D):
    rows = []
    n = len(D["c"])
    for i in range(300, n - 2):
        srv = int(D["t"][i])
        if srv < START or D["hour"][i] in (23, 0):
            continue
        if not np.isfinite(D["atrr"][i]) or not np.isfinite(D["pdh"][i]) or not np.isfinite(D["bwrank"][i]):
            continue
        p = period(srv)
        if p is None:
            continue
        e = i + 1
        A = D["atr"][i]
        for d in (1, -1):
            entry = D["o"][e] + (D["sp"][e] if d == 1 else 0.0)
            t = gp.run_trade(D, e, d, entry, entry - d * A, entry + d * 2 * A, 48)
            if t is None:
                continue
            rows.append(dict(i=i, x=t["x"], d=d, r=t["rh"], r15=t["rh15"], p=p, year=int(np.datetime64(srv, "s").astype("datetime64[Y]").astype(int) + 1970),
                             hour=int(D["hour"][i]), mon=int(D["mon"][i]), f=factors(D, i, d)))
    return rows


def select_states(rows):
    sel = [r for r in rows if r["p"] == "chọn"]
    names = sorted(sel[0]["f"])
    out = []
    for fn in names:
        for st in sorted({r["f"][fn] for r in sel}):
            deltas, share = [], np.mean([r["f"][fn] == st for r in sel])
            for y in SEL_YEARS:
                for d in (1, -1):
                    cell = [r for r in sel if r["year"] == y and r["d"] == d]
                    a = [r["r"] for r in cell if r["f"][fn] == st]
                    b = [r["r"] for r in cell if r["f"][fn] != st]
                    deltas.append(np.mean(a) - np.mean(b) if a and b else np.nan)
            deltas = np.array(deltas)
            mean = float(np.nanmean(deltas))
            kind = None
            if ROUND_B:      # G147b: at most one of the 8 cells against the sign or empty
                if share >= MIN_SHARE and abs(mean) >= MIN_DELTA:
                    if (~(deltas < 0)).sum() <= 1:
                        kind = "TRÁNH"
                    elif (~(deltas > 0)).sum() <= 1:
                        kind = "ƯU TIÊN"
            elif share >= MIN_SHARE and np.all(np.isfinite(deltas)) and abs(mean) >= MIN_DELTA:
                if np.all(deltas < 0):
                    kind = "TRÁNH"
                elif np.all(deltas > 0):
                    kind = "ƯU TIÊN"
            out.append(dict(factor=fn, state=st, share=round(float(share), 3), delta=round(mean, 3),
                            neg_cells=int((deltas < 0).sum()), kind=kind))
    return out


def confirm(rows, states):
    for s in states:
        if not s["kind"]:
            continue
        res = {}
        for p in ("validate", "test"):
            for d in (1, -1):
                cell = [r for r in rows if r["p"] == p and r["d"] == d]
                a = [r["r"] for r in cell if r["f"][s["factor"]] == s["state"]]
                b = [r["r"] for r in cell if r["f"][s["factor"]] != s["state"]]
                res[f"{p} {'mua' if d == 1 else 'bán'}"] = round(np.mean(a) - np.mean(b), 3) if a and b else None
        s["kiểm"] = res
        vals = [v for v in res.values() if v is not None]
        sign = -1 if s["kind"] == "TRÁNH" else 1
        s["xác nhận"] = len(vals) == 4 and all(sign * v > 0 for v in vals)


def score(r, avoid, favour):
    a = sum(r["f"][f] == s for f, s in avoid)
    b = sum(r["f"][f] == s for f, s in favour)
    return b - a, a


def system(rows, avoid, favour, T):
    out, busy = [], {1: -1, -1: -1}
    for r in sorted(rows, key=lambda z: (z["i"], z["d"])):
        sc, na = score(r, avoid, favour)
        if sc >= T and na == 0 and r["i"] > busy[r["d"]]:
            out.append(r)
            busy[r["d"]] = r["x"]
    return out


def stat(xs):
    xs = list(xs)
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = prepare(g.load("XAUUSD"))
    rows = universe(D)
    print("universe", len(rows), flush=True)
    res = {"vũ trụ": {p: {"mua": stat(r["r"] for r in rows if r["p"] == p and r["d"] == 1),
                          "bán": stat(r["r"] for r in rows if r["p"] == p and r["d"] == -1)} for p, _, _ in PER}}
    states = select_states(rows)
    confirm(rows, states)
    avoid = [(s["factor"], s["state"]) for s in states if s["kind"] == "TRÁNH"]
    favour = [(s["factor"], s["state"]) for s in states if s["kind"] == "ƯU TIÊN"]
    res["trạng thái"] = states
    print("avoid", avoid, "\nfavour", favour, flush=True)
    sel_rows = [r for r in rows if r["p"] == "chọn"]
    pick = {}
    for T in (1, 2, 3, 4):
        s = system(sel_rows, avoid, favour, T)
        pick[T] = (np.mean([r["r"] for r in s]) if len(s) >= 300 else -9, len(s))
    T = max(pick, key=lambda k: pick[k][0])
    res["chọn T"] = {str(k): [round(float(v[0]), 3), v[1]] for k, v in pick.items()}
    res["T"] = T
    sysr = system(rows, avoid, favour, T)
    vt = [r for r in sysr if r["p"] in ("validate", "test")]
    res["hệ thống theo kỳ"] = {p: {"tất cả": stat(r["r"] for r in sysr if r["p"] == p),
                                   "mua": stat(r["r"] for r in sysr if r["p"] == p and r["d"] == 1),
                                   "bán": stat(r["r"] for r in sysr if r["p"] == p and r["d"] == -1)} for p, _, _ in PER}
    res["theo năm"] = {str(y): stat(r["r"] for r in sysr if r["year"] == y) for y in range(2018, 2027)}
    res["validate+test"] = {"mua": stat(r["r"] for r in vt if r["d"] == 1), "bán": stat(r["r"] for r in vt if r["d"] == -1),
                            "tháng không tăng": stat(r["r"] for r in vt if D["down_month"].get(r["mon"])),
                            "phí×1,5": stat(r["r15"] for r in vt),
                            "bỏ 5 lệnh lớn nhất": stat(sorted(r["r"] for r in vt)[:-5])}
    mons = sorted({r["mon"] for r in rows if r["p"] in ("validate", "test")})
    ms = defaultdict(float)
    for r in vt:
        ms[r["mon"]] += r["r"]
    seq = [ms[m] for m in mons]
    res["cửa sổ 6 tháng tệ nhất (R)"] = round(float(min(sum(seq[k:k + 6]) for k in range(len(seq) - 5))), 1)
    # compare: risk profile vs the unfiltered universe in validate+test
    uv = [r for r in rows if r["p"] in ("validate", "test")]
    res["so với vũ trụ (validate+test)"] = {"vũ trụ R/lệnh": round(float(np.mean([r["r"] for r in uv])), 3),
                                           "vũ trụ tỷ lệ chạm SL": round(float(np.mean([r["r"] < -0.9 for r in uv])), 3),
                                           "hệ thống tỷ lệ chạm SL": round(float(np.mean([r["r"] < -0.9 for r in vt])), 3)}
    streak = best = 0
    for r in sorted(vt, key=lambda z: z["i"]):
        streak = streak + 1 if r["r"] < 0 else 0
        best = max(best, streak)
    res["chuỗi thua dài nhất (validate+test)"] = best
    # random control: same period, direction and server hour
    pool = defaultdict(list)
    for r in uv:
        pool[(r["p"], r["d"], r["hour"])].append(r["r"])
    actual = float(np.mean([r["r"] for r in vt]))
    rng = random.Random(147)
    hits = sum(np.mean([rng.choice(pool[(r["p"], r["d"], r["hour"])]) for r in vt]) >= actual for _ in range(RUNS))
    res["p ngẫu nhiên"] = (hits + 1) / (RUNS + 1)
    h = res["hệ thống theo kỳ"]
    ok = (all(h[p]["tất cả"]["n"] >= 100 and h[p]["tất cả"]["mean"] > 0 for p in ("validate", "test"))
          and res["validate+test"]["mua"].get("mean", -1) > 0 and res["validate+test"]["bán"].get("mean", -1) > 0
          and res["validate+test"]["tháng không tăng"]["n"] >= 50 and res["validate+test"]["tháng không tăng"]["mean"] > 0
          and res["p ngẫu nhiên"] <= PVAL and res["validate+test"]["phí×1,5"]["mean"] > 0
          and res["cửa sổ 6 tháng tệ nhất (R)"] >= -15 and res["validate+test"]["bỏ 5 lệnh lớn nhất"]["mean"] > 0)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "trạng thái"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
