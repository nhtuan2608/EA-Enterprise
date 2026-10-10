"""G90: FX swing / higher-timeframe setups. Pre-registered plan: docs/superpowers/plans/2026-10-11-g90-fx-swing.md.
MT5 data only.

  python g90_fx_swing.py build     # data/h1v, data/h4v from the EA exports + the terminal tail; swap rates
  python g90_fx_swing.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-11-g90-fx-swing.md"
MAIN = ("EURUSD", "GBPUSD", "USDJPY")
CROSS = ("EURJPY", "GBPJPY", "AUDJPY")
BROKER = {s: s + "-VIP" for s in MAIN + CROSS}
SWAP_FILE = g.HERE / "data" / "fx_swaps.json"
PERIODS = [("train", g.ts(2010, 1, 1), g.ts(2017, 1, 1)), ("validate", g.ts(2017, 1, 1), g.ts(2021, 1, 1)),
           ("test", g.ts(2021, 1, 1), g.ts(2030, 1, 1))]
KEYS = ("train", "validate", "test")
N_TESTS = 33
RUNS = 1000
for s in MAIN + CROSS:
    g.POINT.setdefault(s, 0.001 if s.endswith("JPY") else 0.00001)
    g.COMMISSION.setdefault(s, 0.009 if s.endswith("JPY") else 0.00006)


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def build():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        raise RuntimeError(mt5.last_error())
    swaps = {}
    try:
        for s in MAIN + CROSS:
            info = mt5.symbol_info(BROKER[s])
            swaps[s] = dict(mode=int(info.swap_mode), long=float(info.swap_long), short=float(info.swap_short),
                            triple=int(info.swap_rollover3days))
            for tf, code in (("H1", mt5.TIMEFRAME_H1), ("H4", mt5.TIMEFRAME_H4)):
                rows = []
                f = g.HERE / "data" / f"bars_{s}_{tf}.csv"
                if f.exists() and s in MAIN:
                    for r in csv.DictReader(open(f)):
                        rows.append((int(r["time"]), r["open"], r["high"], r["low"], r["close"], 0, int(r["spread"])))
                last = rows[-1][0] if rows else 0
                tail = mt5.copy_rates_from_pos(BROKER[s], code, 1, 99000)
                rows += [(int(x["time"]), x["open"], x["high"], x["low"], x["close"], int(x["tick_volume"]), int(x["spread"]))
                         for x in (tail if tail is not None else []) if int(x["time"]) > last]
                out = g.HERE / "data" / f"{tf.lower()}v" / f"{s}.csv"
                out.parent.mkdir(exist_ok=True)
                with open(out, "w", newline="") as fh:
                    w = csv.writer(fh)
                    w.writerow(["time", "open", "high", "low", "close", "tickvol", "spread"])
                    w.writerows(rows)
                d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
                print(f"{s} {tf}: {len(rows)} bars {d(rows[0][0])} .. {d(rows[-1][0])}")
    finally:
        mt5.shutdown()
    SWAP_FILE.write_text(json.dumps(swaps, indent=1))
    print(swaps)


_D: dict = {}


def load(tf, s):
    key = (tf, s)
    if key not in _D:
        g.set_tf(tf)
        g.GAP_AWARE = True
        D = g.load(s)
        D["tf"], D["sym"] = tf, s
        D["bs"] = {"H1": 3600, "H4": 14400}[tf]
        _D[key] = D
    return _D[key]


def period(utc):
    for n, a, z in PERIODS:
        if a <= utc < z:
            return n
    return "none"


# ---------------------------------------------------------------------------
# costs
# ---------------------------------------------------------------------------
_SW = None


def swap_r(D, t):
    """Swap for the nights held (current broker rate, points mode), in R (+ credit, - cost)."""
    global _SW
    if _SW is None:
        _SW = json.loads(SWAP_FILE.read_text()) if SWAP_FILE.exists() else {}
    sw = _SW.get(D["sym"])
    if not sw or sw["mode"] != 1:
        return 0.0
    pts = sw["long"] if t["d"] == 1 else sw["short"]
    d0, d1 = t["srv_in"] // 86400, t["srv_out"] // 86400
    nights = 0
    for day in range(d0 + 1, d1 + 1):
        wd = datetime.fromtimestamp(day * 86400, timezone.utc).weekday()     # weekday of the day being entered
        if wd in (5, 6):
            continue
        nights += 3 if wd == sw["triple"] else 1   # MT5 3 = Wednesday -> rollover into Thursday (Python 3)
    return pts * g.POINT[D["sym"]] * nights / t["risk"]


# ---------------------------------------------------------------------------
# walker
# ---------------------------------------------------------------------------
def walk(D, i, d, dist, ex):
    """Market entry at the next open; stop at dist; exits by ex = dict(tp, ema, mr, bars, until)."""
    o, hh, ll, c, sp, E = D["o"], D["h"], D["l"], D["c"], D["sp"], D["E"]
    n = len(c)
    e0 = i + 1
    if e0 >= n:
        return None
    entry = o[e0] + (sp[e0] if d == 1 else 0.0)
    sl = entry - d * dist
    tp = entry + d * ex["tp"] * dist if ex.get("tp") else None
    best = entry
    exit_px, x, reason = None, None, "TIME"
    for j in range(e0, min(n, e0 + ex["bars"])):
        sj = sp[j] if d == -1 else 0.0
        bh, bl, bo = hh[j] + sj, ll[j] + sj, o[j] + sj
        if (d == 1 and bl <= sl) or (d == -1 and bh >= sl):
            exit_px, x, reason = (min(sl, bo) if d == 1 else max(sl, bo)), j, "SL"
            break
        if tp is not None and ((d == 1 and bh >= tp) or (d == -1 and bl <= tp)):
            exit_px, x, reason = (max(tp, bo) if d == 1 else min(tp, bo)), j, "TP"
            break
        best = max(best, hh[j]) if d == 1 else min(best, bl)
        out = False
        if ex.get("ema"):
            ema = E[100] if d * (best - entry) >= 3 * dist else E[55]
            out = d * (c[j] - ema[j]) < 0
        if ex.get("mr"):
            out = out or d * (c[j] - E[21][j]) >= 0
        if ex.get("until") and D["utc"][j] + D["bs"] >= ex["until"]:
            x, exit_px, reason = j, c[j] + sj, "SESSION"
            break
        if out and j + 1 < n:
            x = j + 1
            exit_px = o[x] + (sp[x] if d == -1 else 0.0)
            reason = "EXIT"
            break
    if exit_px is None:
        x = min(n - 1, e0 + ex["bars"] - 1)
        exit_px = c[x] + (sp[x] if d == -1 else 0.0)
    r = d * (exit_px - entry) / dist - D["comm"] / dist
    t = {"i": int(i), "d": d, "utc": int(D["utc"][i]), "r": float(r), "risk": float(dist), "reason": reason,
         "dist_atr": float(dist / D["atr"][i]), "e0": int(e0), "x": int(x), "sp_in": float(sp[e0]), "sp_out": float(sp[x]),
         "srv_in": int(D["t"][e0]), "srv_out": int(D["t"][x]), "eout": int(D["utc"][x])}
    t["rh"] = h.harsh(t, D) + swap_r(D, t)
    t["p"] = period(t["utc"])
    return t


# ---------------------------------------------------------------------------
# setups: each returns a list of (i, d, dist, ex)
# ---------------------------------------------------------------------------
def setup_A(D, k):
    c, E, atr = D["c"], D["E"], D["atr"]
    z = (c - E[55]) / np.maximum(atr, 1e-12)
    out = []
    for i in range(300, len(c) - 1):
        if z[i] <= -k < z[i - 1]:
            out.append((i, 1, 1.5 * atr[i], dict(mr=True, bars=24)))
        elif z[i] >= k > z[i - 1]:
            out.append((i, -1, 1.5 * atr[i], dict(mr=True, bars=24)))
    return out


def setup_B(D, variant):
    hh, ll, c, utc, atr = D["h"], D["l"], D["c"], D["utc"], D["atr"]
    out = []
    day_hi, day_lo, cur_day, done = -np.inf, np.inf, None, False
    for i in range(300, len(c) - 1):
        day, hour = utc[i] // 86400, (utc[i] // 3600) % 24
        if day != cur_day:
            cur_day, day_hi, day_lo, done = day, -np.inf, np.inf, False
        if hour <= 6:
            day_hi, day_lo = max(day_hi, hh[i]), min(day_lo, ll[i])
            continue
        if done or not (7 <= hour <= 11) or not np.isfinite(day_hi):
            continue
        d = 1 if c[i] > day_hi else -1 if c[i] < day_lo else 0
        if d == 0:
            continue
        done = True
        stop = day_lo if d == 1 else day_hi
        dist = abs(c[i] - stop)
        if dist > 2.5 * atr[i]:
            continue
        dist = max(dist, 0.5 * atr[i])
        until = day * 86400 + 20 * 3600 + (86400 if variant == "B2" else 0)
        out.append((i, d, dist, dict(tp=2.0 if variant == "B1" else 3.0, until=until, bars=48)))
    return out


def setup_C(D, variant):
    hh, ll, c, E, atr = D["h"], D["l"], D["c"], D["E"], D["atr"]
    out = []
    for i in range(300, len(c) - 1):
        for d in (1, -1):
            if d == 1:
                trend = E[21][i] > E[55][i] > E[100][i] and c[i] > E[200][i] and D["d1_side"][i] == 1
                pulled = any(ll[j] <= E[55][j] for j in range(i - 3, i))
                trig = c[i] > E[21][i] and c[i] > hh[i - 1]
                ext = float(ll[i - 4:i + 1].min()) - 0.1 * atr[i]
            else:
                trend = E[21][i] < E[55][i] < E[100][i] and c[i] < E[200][i] and D["d1_side"][i] == -1
                pulled = any(hh[j] >= E[55][j] for j in range(i - 3, i))
                trig = c[i] < E[21][i] and c[i] < ll[i - 1]
                ext = float(hh[i - 4:i + 1].max()) + 0.1 * atr[i]
            if not (trend and pulled and trig):
                continue
            dist = d * (c[i] - ext)
            if dist <= 0 or dist > 3 * atr[i]:
                continue
            dist = max(dist, atr[i])
            ex = dict(ema=True, tp=6.0, bars=240) if variant == "C1" else dict(tp=2.0, bars=60)
            out.append((i, d, dist, ex))
    return out


def setup_D(D):
    g.COMP_BARS, g.ADX_LOW, g.DI_GAP, g.ADX_RISE = 8, 20.0, 6.0, 10.0
    out = []
    for i, d in g.signals(D):
        if D["h4_side"][i] != d:
            continue
        a0 = i - 8
        ext = float(D["l"][a0:i + 1].min()) - 0.1 * D["atr"][i] if d == 1 else float(D["h"][a0:i + 1].max()) + 0.1 * D["atr"][i]
        dist = d * (D["c"][i] - ext)
        if dist <= 0 or dist > 4 * D["atr"][i]:
            continue
        out.append((i, d, max(dist, D["atr"][i]), dict(ema=True, tp=8.0, bars=240)))
    return out


SETS = ([("A", tf, f"k{k}", (lambda D, k=k: setup_A(D, k))) for tf in ("H1", "H4") for k in (2.0, 2.5, 3.0)] +
        [("B", "H1", v, (lambda D, v=v: setup_B(D, v))) for v in ("B1", "B2")] +
        [("C", "H4", v, (lambda D, v=v: setup_C(D, v))) for v in ("C1", "C2")] +
        [("D", "H4", "S07", setup_D)])


def book(D, sigs):
    out, free = [], 0
    for i, d, dist, ex in sigs:
        if i < free:
            continue
        t = walk(D, i, d, dist, ex)
        if t is None:
            continue
        t["ex"] = ex
        out.append(t)
        free = t["x"] + 1
    return out


def stats(trs):
    return {q: (len([t for t in trs if t["p"] == q]), float(np.mean([t["rh"] for t in trs if t["p"] == q])) if any(t["p"] == q for t in trs) else 0.0)
            for q in KEYS}


def rand_job(arg):
    tf, s, rows, seed, runs = arg
    D = load(tf, s)
    rng = np.random.default_rng(seed)
    n = len(D["c"])
    pools = {}
    for name, a, z in PERIODS:
        idx = np.nonzero((D["utc"] >= a) & (D["utc"] < z))[0]
        pools[name] = idx[(idx > 300) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            if not len(pools[t["p"]]):
                continue
            i = int(rng.choice(pools[t["p"]]))
            ex = dict(t["ex"])
            if ex.get("until"):
                ex["until"] = int(D["utc"][i]) + (ex["until"] - t["utc"])
            tr = walk(D, i, t["d"], t["dist_atr"] * D["atr"][i], ex)
            if tr:
                rs.append(tr["rh"])
        means.append(float(np.mean(rs)) if rs else 0.0)
    return means


def p_random(tf, s, trs):
    rows = [dict(p=t["p"], d=t["d"], dist_atr=t["dist_atr"], ex=t["ex"], utc=t["utc"]) for t in trs if t["p"] in KEYS]
    real = float(np.mean([t["rh"] for t in trs if t["p"] in KEYS]))
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(tf, s, rows, 9000 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def portfolio(trs, risk=0.01):
    rows = sorted([(t["rh"], t["eout"]) for t in trs], key=lambda z: z[1])
    if len(rows) < 20:
        return None
    eq = pk = 1.0
    dd = 0.0
    for r, _ in rows:
        eq *= 1 + risk * r
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    yrs = (rows[-1][1] - rows[0][1]) / (365.25 * 86400)
    return (eq ** (1 / yrs) - 1) * 100, dd * 100


def main():
    L = ["# G90: Setup swing / khung lớn cho FX — kết quả", "",
         "Kế hoạch: `plans/2026-10-11-g90-fx-swing.md`. Chi phí khắt khe G68 + swap qua đêm (mức swap hiện tại của broker). "
         "Ô: số lệnh / R mỗi lệnh. Kỳ: train 2010–2016, validate 2017–2020, test 2021–10/2026.", "",
         "| Setup | Khung | Biến thể | Cặp | Train | Validate | Test | Đạt điều 1–2 |", "|---|---|---|---|---|---|---|---|"]
    res = {}
    for name, tf, var, fn in SETS:
        for s in MAIN:
            D = load(tf, s)
            trs = book(D, fn(D))
            res[(name, tf, var, s)] = trs
            st = stats(trs)
            ok12 = all(st[q][0] and st[q][1] > 0 for q in KEYS) and sum(st[q][0] for q in KEYS) >= 100
            L.append(f"| {name} | {tf} | {var} | {s} | " + " | ".join(f"{st[q][0]} / {st[q][1]:+.3f}" for q in KEYS) +
                     f" | {'✓' if ok12 else ''} |")
        sys.stdout.buffer.write(f"{name} {tf} {var}\n".encode()); sys.stdout.flush()
    # pooled per setup x variant (criterion 4)
    L += ["", "### Gộp 3 cặp (điều 4)", "", "| Setup | Khung | Biến thể | Train | Validate | Test |", "|---|---|---|---|---|---|"]
    pooled_ok = {}
    for name, tf, var, _ in SETS:
        trs = [t for s in MAIN for t in res[(name, tf, var, s)]]
        st = stats(trs)
        pooled_ok[(name, tf, var)] = all(st[q][0] and st[q][1] > 0 for q in KEYS)
        L.append(f"| {name} | {tf} | {var} | " + " | ".join(f"{st[q][0]} / {st[q][1]:+.3f}" for q in KEYS) + " |")
    passed = []
    L += ["", "### Bộ qua điều 1–2: kiểm tra ngẫu nhiên và điều 4", ""]
    for key, trs in res.items():
        st = stats(trs)
        if not (all(st[q][0] and st[q][1] > 0 for q in KEYS) and sum(st[q][0] for q in KEYS) >= 100):
            continue
        name, tf, var, s = key
        rm, p = p_random(tf, s, trs)
        ok = p < 0.05 / N_TESTS and pooled_ok[(name, tf, var)]
        L.append(f"- {name} {tf} {var} {s}: ngẫu nhiên TB {rm:+.3f}, p = {p:.4f}; gộp 3 cặp dương cả 3 kỳ: "
                 f"{'có' if pooled_ok[(name, tf, var)] else 'không'} → **{'ĐẠT' if ok else 'không đạt'}**")
        if ok:
            passed.append(key)
    if not passed:
        L += ["", "**Không bộ nào đạt đủ 4 điều.**", ""]
    else:
        L += ["", f"**Đạt: {', '.join(' '.join(k) for k in passed)}.**", ""]
        allt = [t for k in passed for t in res[k]]
        pf = portfolio(allt)
        if pf:
            L.append(f"Sổ gộp các bộ đạt, 1%/lệnh, 2010–2026: {pf[0]:+.1f}%/năm, DD lớn nhất {pf[1]:.0f}%.")
        L += ["", "Kiểm tra phụ trên JPY chéo (02/2024–):", ""]
        for name, tf, var, s in passed:
            fn = next(f for n_, t_, v_, f in SETS if (n_, t_, v_) == (name, tf, var))
            for cs in CROSS:
                D = load(tf, cs)
                trs = book(D, fn(D))
                x = [t["rh"] for t in trs]
                L.append(f"- {name} {tf} {var} trên {cs}: {len(x)} lệnh, {np.mean(x) if x else 0:+.3f}R/lệnh")
        L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build() if len(sys.argv) > 1 and sys.argv[1] == "build" else main()
