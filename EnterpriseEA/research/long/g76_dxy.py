"""G76: S07 on DXY (broker USDX.) as a filter / entry for gold. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g76-dxy-s07.md. MT5 data only.

  python g76_dxy.py build    # data/m30v/DXY.csv from the raw MT5 export + the terminal tail
  python g76_dxy.py
"""
from __future__ import annotations

import csv
import glob
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g76-dxy-s07.md"
RAW = Path(r"D:\Work\Private\AI APP\Trading-with-AI\input\raw\DXY")
START = g.ts(2021, 9, 14)
PERIODS = [("train", START, g.ts(2024, 1, 1)), ("validate", g.ts(2024, 1, 1), g.ts(2025, 7, 1)),
           ("test", g.ts(2025, 7, 1), g.ts(2026, 7, 1)), ("examples", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
DECIDE = ("train", "validate", "test")
LOOK_F1, NEAR_F3 = 8, 4
RUNS = 200
g.POINT["DXY"] = 0.001
g.COMMISSION["DXY"] = 0.0


def build():
    f = sorted(glob.glob(str(RAW / "USDX._M30_*.csv")))[-1]
    rows = []
    with open(f, newline="") as fh:
        rd = csv.reader(fh, delimiter="\t")
        next(rd)
        for r in rd:
            t = datetime.strptime(r[0] + " " + r[1], "%Y.%m.%d %H:%M:%S").replace(tzinfo=timezone.utc)
            rows.append((int(t.timestamp()), r[2], r[3], r[4], r[5], r[6], r[8]))
    import MetaTrader5 as mt5
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        raise RuntimeError(mt5.last_error())
    try:
        tail = mt5.copy_rates_from_pos("USDX.", mt5.TIMEFRAME_M30, 1, 99000)
    finally:
        mt5.shutdown()
    last = rows[-1][0]
    rows += [(int(x["time"]), x["open"], x["high"], x["low"], x["close"], int(x["tick_volume"]), int(x["spread"]))
             for x in (tail if tail is not None else []) if int(x["time"]) > last]
    out = g.HERE / "data" / "m30v" / "DXY.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "tickvol", "spread"])
        w.writerows(rows)
    d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")
    print(f"DXY M30: {len(rows)} bars {d(rows[0][0])} .. {d(rows[-1][0])}")


def period(utc):
    for n, a, z in PERIODS:
        if a <= utc < z:
            return n
    return "none"


def setup():
    g.set_tf("M30")
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = 8, 4, 240
    g.ADX_LOW, g.DI_GAP, g.ADX_RISE, g.GAP_AWARE = 20.0, 6.0, 10.0, True
    G = g.load("XAUUSD")
    X = g.load("DXY")
    return G, X


def align(G, X):
    """Index of the DXY bar with the same server time as each gold bar (-1 when missing)."""
    pos = {int(t): k for k, t in enumerate(X["t"])}
    return np.array([pos.get(int(t), -1) for t in G["t"]], dtype=np.int64)


def dxy_signals(X):
    return {i: d for i, d in g.signals(X) if g.block_ok(X, i, d, "B6")}


def finish(G, t):
    t["srv_in"], t["srv_out"] = int(G["t"][t["e0"]]), int(G["t"][t["x"]])
    t["rh"] = h.harsh(t, G)
    t["p"] = period(t["utc"])
    return t


def gold_trades(G, sigs):
    return [finish(G, t) for t in g.trades("XAUUSD", "E2X", 8.0, None, sigs)]


def variants(G, X, amap):
    base = [(i, d) for i, d in g.signals(G) if g.block_ok(G, i, d, "B6") and G["utc"][i] >= START]
    xs = dxy_signals(X)
    x_idx = sorted(xs)
    ehi = np.maximum.reduce([X["E"][n] for n in (21, 55, 100, 200)])
    elo = np.minimum.reduce([X["E"][n] for n in (21, 55, 100, 200)])

    def dxy_near(k, lo, hi, want):
        a = int(np.searchsorted(x_idx, k + lo))
        z = int(np.searchsorted(x_idx, k + hi, side="right"))
        return any(xs[x_idx[q]] == want for q in range(a, z))

    out = {"B0": base, "F1": [], "F2": [], "F3": [], "T1": []}
    for i, d in base:
        k = amap[i]
        if k < 0:
            continue
        if not dxy_near(k, -LOOK_F1, 0, d):           # DXY broke the same way as gold (against gold)
            out["F1"].append((i, d))
        if (d == 1 and X["c"][k] < elo[k]) or (d == -1 and X["c"][k] > ehi[k]):
            out["F2"].append((i, d))
        if dxy_near(k, -NEAR_F3, NEAR_F3, -d):
            out["F3"].append((i, d))
    gpos = {int(t): k for k, t in enumerate(G["t"])}
    for k, dx in xs.items():
        i = gpos.get(int(X["t"][k]), -1)
        if i < 400 or i >= len(G["t"]) - 1 or G["utc"][i] < START:
            continue
        d = -dx
        if G["h4_side"][i] == d:
            out["T1"].append((i, d))
    out["T1"].sort()
    return {k: gold_trades(G, v) for k, v in out.items()}


def stats(trs, d):
    x = [t for t in trs if t["d"] == d]
    per = {k: g.stats([t["rh"] for t in x if t["p"] == k]) for k, _, _ in PERIODS}
    dec = [t for t in x if t["p"] in DECIDE]
    rh = [t["rh"] for t in dec]
    dd = h.dd_p90([{"utc": t["utc"], "r": t["rh"]} for t in dec], 0.015) if len(dec) >= 20 else float("nan")
    return {"per": per, "n": len(dec), "exp": float(np.mean(rh)) if rh else 0.0, "total": float(np.sum(rh)) if rh else 0.0,
            "dd": dd, "trades": dec}


def rand_job(arg):
    rows, seed, runs = arg
    G, _ = setup()
    rng = np.random.default_rng(seed)
    n = len(G["c"])
    pools = {}
    for name, a, z in PERIODS:
        idx = np.nonzero((G["utc"] >= a) & (G["utc"] < z))[0]
        pools[name] = idx[(idx > 400) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            i = int(rng.choice(pools[t["p"]]))
            tr = g.walk(G, i, t["d"], "E2X", 8.0, None, t["dist_atr"])
            if tr:
                tr["srv_in"], tr["srv_out"] = int(G["t"][tr["e0"]]), int(G["t"][tr["x"]])
                rs.append(h.harsh(tr, G))
        means.append(float(np.mean(rs)))
    return means


def p_random(trs):
    if len(trs) < 10:
        return float("nan"), float("nan")
    real = float(np.mean([t["rh"] for t in trs]))
    lite = [{"p": t["p"], "d": t["d"], "dist_atr": t["dist_atr"]} for t in trs]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(lite, 7600 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def merged(G, a, b):
    """B0 and T1 signals together under one cool-down (first come)."""
    sig = sorted({(t["i"], t["d"]) for t in a} | {(t["i"], t["d"]) for t in b})
    return gold_trades(G, sig)


def cell(s):
    return f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"


def main():
    G, X = setup()
    amap = align(G, X)
    cover = float(np.mean(amap[G["utc"] >= START] >= 0))
    res = variants(G, X, amap)
    L = ["# G76: S07 trên DXY để tìm điểm vào cho vàng — kết quả", "",
         f"Kế hoạch: `plans/2026-10-10-g76-dxy-s07.md`. Vàng M30, DXY = USDX. của broker (cùng giờ server). "
         f"Nến vàng có nến DXY cùng giờ: {cover:.1%}. DXY: {len(X['t'])} nến M30 tới "
         f"{datetime.fromtimestamp(int(X['utc'][-1]), timezone.utc):%d/%m/%Y}. Chi phí khắt khe G68. Gộp = train + validate + test.", "",
         "| Chiều vàng | Bản | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | DD p90 1 năm (1,5%) | Ngẫu nhiên (TB / p) | Kết luận |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    names = {"B0": "B0 vàng gốc", "F1": "F1 bỏ khi DXY bung cùng chiều", "F2": "F2 DXY phía ngược 4 EMA",
             "F3": "F3 DXY bung ngược chiều ±4 nến", "T1": "T1 vào vàng theo tín hiệu DXY"}
    for d, dn in ((1, "Mua"), (-1, "Bán")):
        b = stats(res["B0"], d)
        for k in ("B0", "F1", "F2", "F3", "T1"):
            s = stats(res[k], d)
            rm, p = p_random(s["trades"]) if k != "B0" else p_random(b["trades"])
            verdict = ""
            if k in ("F1", "F2", "F3"):
                ok = (s["per"]["train"]["exp"] >= b["per"]["train"]["exp"] + 0.05 and
                      s["per"]["validate"]["exp"] >= b["per"]["validate"]["exp"] + 0.05 and
                      s["n"] >= 0.5 * b["n"] and s["per"]["test"]["exp"] >= b["per"]["test"]["exp"] and
                      s["total"] >= 0.8 * b["total"])
                verdict = "**giữ**" if ok else "không"
            elif k == "T1":
                ok = all(s["per"][q]["n"] and s["per"][q]["exp"] > 0 for q in DECIDE) and (not np.isnan(p)) and p < 0.025
                verdict = "**có hiệu quả**" if ok else "không"
            pr = s["per"]
            dd = "—" if np.isnan(s["dd"]) else f"{s['dd']:.0%}"
            L.append(f"| {dn} | {names[k]} | {cell(pr['train'])} | {cell(pr['validate'])} | {cell(pr['test'])} | {cell(pr['examples'])} | "
                     f"{s['n']} | {s['exp']:+.3f} | {s['total']:+.1f} | {dd} | "
                     f"{'—' if np.isnan(p) else f'{rm:+.3f} / {p:.3f}'} | {verdict} |")
        mg = stats(merged(G, [t for t in res["B0"] if t["d"] == d], [t for t in res["T1"] if t["d"] == d]), d)
        mdd = "—" if np.isnan(mg["dd"]) else f"{mg['dd']:.0%}"
        L.append(f"| {dn} | B0 + T1 (tham khảo) | {cell(mg['per']['train'])} | {cell(mg['per']['validate'])} | {cell(mg['per']['test'])} | "
                 f"{cell(mg['per']['examples'])} | {mg['n']} | {mg['exp']:+.3f} | {mg['total']:+.1f} | {mdd} | — | — |")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    build() if len(sys.argv) > 1 and sys.argv[1] == "build" else main()
