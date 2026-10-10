"""G77: S07 on DXY M15 / M30 as a filter / entry for gold M15 / M30, causal only. Pre-registered plan:
docs/superpowers/plans/2026-10-10-g77-dxy-m15-m30.md. MT5 data only.

  python g77_dxy_tf.py build    # data/m15v/DXY.csv and data/m30v/DXY.csv (raw MT5 export + terminal tail)
  python g77_dxy_tf.py
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
import g76_dxy as g76  # noqa: E402  (PERIODS, period, POINT/COMMISSION for DXY)

REPORT = g.HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-10-g77-dxy-m15-m30.md"
SEC = {"M15": 900, "M30": 1800}
CFG = {"M15": dict(comp=16, cool=8, hold=480), "M30": dict(comp=8, cool=4, hold=240)}
COMBOS = [("M15", "M15"), ("M30", "M15"), ("M15", "M30"), ("M30", "M30")]
F1_SEC, F3_SEC = 4 * 3600, 2 * 3600
DECIDE = g76.DECIDE
N_TESTS = 32
RUNS = 200


def build(tf):
    f = sorted(glob.glob(str(g76.RAW / f"USDX._{tf}_*.csv")))[-1]
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
        tail = mt5.copy_rates_from_pos("USDX.", getattr(mt5, "TIMEFRAME_" + tf), 1, 99000)
    finally:
        mt5.shutdown()
    last = rows[-1][0]
    rows += [(int(x["time"]), x["open"], x["high"], x["low"], x["close"], int(x["tick_volume"]), int(x["spread"]))
             for x in (tail if tail is not None else []) if int(x["time"]) > last]
    out = g.HERE / "data" / f"{tf.lower()}v" / "DXY.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "tickvol", "spread"])
        w.writerows(rows)
    d = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")
    print(f"DXY {tf}: {len(rows)} bars {d(rows[0][0])} .. {d(rows[-1][0])}")


def configure(tf):
    g.set_tf(tf)
    c = CFG[tf]
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = c["comp"], c["cool"], c["hold"]
    g.ADX_LOW, g.DI_GAP, g.ADX_RISE, g.GAP_AWARE = 20.0, 6.0, 10.0, True


def dxy(tf):
    configure(tf)
    X = g.load("DXY")
    sig = [(i, d) for i, d in g.signals(X) if g.block_ok(X, i, d, "B6")]
    close = X["t"] + SEC[tf]
    ehi = np.maximum.reduce([X["E"][n] for n in (21, 55, 100, 200)])
    elo = np.minimum.reduce([X["E"][n] for n in (21, 55, 100, 200)])
    return dict(tf=tf, close=close, c=X["c"], ehi=ehi, elo=elo,
                sig_close=np.array([close[i] for i, _ in sig], dtype=np.int64), sig_dir=np.array([d for _, d in sig]))


def gold(tf):
    configure(tf)
    return g.load("XAUUSD")


def finish(G, t):
    t["srv_in"], t["srv_out"] = int(G["t"][t["e0"]]), int(G["t"][t["x"]])
    t["rh"] = h.harsh(t, G)
    t["p"] = g76.period(t["utc"])
    return t


def any_dxy(X, lo, hi, want):
    a = int(np.searchsorted(X["sig_close"], lo, side="right"))
    z = int(np.searchsorted(X["sig_close"], hi, side="right"))
    return bool(np.any(X["sig_dir"][a:z] == want))


def variants(gtf, X, G):
    gclose = G["t"] + SEC[gtf]
    base = [(i, d) for i, d in g.signals(G) if g.block_ok(G, i, d, "B6") and G["utc"][i] >= g76.START]
    out = {"B0": base, "F1": [], "F2": [], "F3": [], "F3x": [], "T1": []}
    for i, d in base:
        tc = int(gclose[i])
        k = int(np.searchsorted(X["close"], tc, side="right")) - 1     # latest DXY bar closed by tc
        if k < 0 or tc - X["close"][k] > SEC[X["tf"]]:
            continue
        if not any_dxy(X, tc - F1_SEC, tc, d):
            out["F1"].append((i, d))
        if (d == 1 and X["c"][k] < X["elo"][k]) or (d == -1 and X["c"][k] > X["ehi"][k]):
            out["F2"].append((i, d))
        if any_dxy(X, tc - F3_SEC, tc, -d):
            out["F3"].append((i, d))
        if any_dxy(X, tc - F3_SEC, tc + F3_SEC, -d):                   # G76-style, looks ahead (report only)
            out["F3x"].append((i, d))
    for tc, dx in zip(X["sig_close"], X["sig_dir"]):
        i = int(np.searchsorted(gclose, tc, side="right")) - 1         # latest gold bar closed by the DXY close
        if i < 400 or i >= len(G["t"]) - 1 or G["utc"][i] < g76.START or tc - gclose[i] > SEC[gtf]:
            continue
        d = -int(dx)
        if G["h4_side"][i] == d:
            out["T1"].append((i, d))
    out["T1"] = sorted(set(out["T1"]))
    return {k: [finish(G, t) for t in g.trades("XAUUSD", "E2X", 8.0, None, v)] for k, v in out.items()}


def stats(trs, d):
    x = [t for t in trs if t["d"] == d]
    per = {k: g.stats([t["rh"] for t in x if t["p"] == k]) for k, _, _ in g76.PERIODS}
    dec = [t for t in x if t["p"] in DECIDE]
    rh = [t["rh"] for t in dec]
    dd = h.dd_p90([{"utc": t["utc"], "r": t["rh"]} for t in dec], 0.015) if len(dec) >= 20 else float("nan")
    return {"per": per, "n": len(dec), "exp": float(np.mean(rh)) if rh else 0.0, "total": float(np.sum(rh)) if rh else 0.0,
            "dd": dd, "trades": dec}


def rand_job(arg):
    gtf, rows, seed, runs = arg
    G = gold(gtf)
    rng = np.random.default_rng(seed)
    n = len(G["c"])
    pools = {}
    for name, a, z in g76.PERIODS:
        idx = np.nonzero((G["utc"] >= a) & (G["utc"] < z))[0]
        pools[name] = idx[(idx > 400) & (idx < n - 2)]
    means = []
    for _ in range(runs):
        rs = []
        for t in rows:
            tr = g.walk(G, int(rng.choice(pools[t["p"]])), t["d"], "E2X", 8.0, None, t["dist_atr"])
            if tr:
                tr["srv_in"], tr["srv_out"] = int(G["t"][tr["e0"]]), int(G["t"][tr["x"]])
                rs.append(h.harsh(tr, G))
        means.append(float(np.mean(rs)))
    return means


def p_random(gtf, trs):
    if len(trs) < 10:
        return float("nan"), float("nan")
    real = float(np.mean([t["rh"] for t in trs]))
    lite = [{"p": t["p"], "d": t["d"], "dist_atr": t["dist_atr"]} for t in trs]
    with Pool(10) as pool:
        sims = [m for ch in pool.map(rand_job, [(gtf, lite, 7700 + k, RUNS // 10) for k in range(10)]) for m in ch]
    return float(np.mean(sims)), float(np.mean(np.array(sims) >= real))


def cell(s):
    return f"{s['n']} / {s['exp']:+.3f}" if s["n"] else "—"


NAMES = {"B0": "B0 vàng gốc", "F1": "F1 bỏ khi DXY bung cùng chiều (4 giờ trước)", "F2": "F2 DXY phía ngược 4 EMA",
         "F3": "F3 DXY bung ngược chiều (2 giờ trước)", "F3x": "F3 kiểu G76 ±2 giờ (nhìn tương lai, chỉ tham khảo)",
         "T1": "T1 vào vàng theo tín hiệu DXY"}


def main():
    L = ["# G77: S07 trên DXY M15 / M30 để tìm điểm vào vàng M15 / M30 — kết quả", "",
         "Kế hoạch: `plans/2026-10-10-g77-dxy-m15-m30.md`. DXY = USDX. của broker, cùng giờ server. Chỉ dùng nến DXY đã đóng "
         "trước hoặc cùng lúc nến tín hiệu vàng (trừ dòng F3 kiểu G76). Chi phí khắt khe G68. Gộp = train + validate + test.", ""]
    found = []
    for gtf, xtf in COMBOS:
        X = dxy(xtf)
        G = gold(gtf)
        res = variants(gtf, X, G)
        L += [f"## Vàng {gtf} × DXY {xtf}", "",
              "| Chiều vàng | Bản | Train | Validate | Test | 07/2026– | Gộp n | Gộp R/lệnh | Tổng R | DD p90 1 năm (1,5%) | Ngẫu nhiên (TB / p) | Kết luận |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d, dn in ((1, "Mua"), (-1, "Bán")):
            b = stats(res["B0"], d)
            for k in ("B0", "F1", "F2", "F3", "F3x", "T1"):
                s = stats(res[k], d)
                rm, p = p_random(gtf, s["trades"]) if k in ("B0", "T1") else (float("nan"), float("nan"))
                verdict = ""
                if k in ("F1", "F2", "F3"):
                    ok = (s["per"]["train"]["exp"] >= b["per"]["train"]["exp"] + 0.05 and
                          s["per"]["validate"]["exp"] >= b["per"]["validate"]["exp"] + 0.05 and
                          s["n"] >= 0.5 * b["n"] and s["per"]["test"]["exp"] >= b["per"]["test"]["exp"] and
                          s["total"] >= 0.8 * b["total"])
                    verdict = "**giữ**" if ok else "không"
                elif k == "T1":
                    ok = all(s["per"][q]["n"] and s["per"][q]["exp"] > 0 for q in DECIDE) and (not np.isnan(p)) and p < 0.05 / N_TESTS
                    verdict = "**có hiệu quả**" if ok else "không"
                if verdict.startswith("**"):
                    found.append(f"vàng {gtf} × DXY {xtf}, {dn}, {k}")
                pr = s["per"]
                dd = "—" if np.isnan(s["dd"]) else f"{s['dd']:.0%}"
                rnd = "—" if np.isnan(p) else f"{rm:+.3f} / {p:.3f}"
                L.append(f"| {dn} | {NAMES[k]} | {cell(pr['train'])} | {cell(pr['validate'])} | {cell(pr['test'])} | "
                         f"{cell(pr['examples'])} | {s['n']} | {s['exp']:+.3f} | {s['total']:+.1f} | {dd} | {rnd} | {verdict} |")
            sig = sorted({(t["i"], t["d"]) for t in res["B0"] + res["T1"] if t["d"] == d})
            mg = stats([finish(G, t) for t in g.trades("XAUUSD", "E2X", 8.0, None, sig)], d)
            mdd = "—" if np.isnan(mg["dd"]) else f"{mg['dd']:.0%}"
            L.append(f"| {dn} | B0 + T1 (tham khảo) | {cell(mg['per']['train'])} | {cell(mg['per']['validate'])} | "
                     f"{cell(mg['per']['test'])} | {cell(mg['per']['examples'])} | {mg['n']} | {mg['exp']:+.3f} | {mg['total']:+.1f} | {mdd} | — | — |")
        L.append("")
        sys.stdout.buffer.write((f"done {gtf} x {xtf}\n").encode()); sys.stdout.flush()
    L += [f"**Theo tiêu chí: {'đạt — ' + '; '.join(found) if found else 'không bản nào đạt'}.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build("M15"); build("M30")
    else:
        main()
