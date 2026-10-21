"""G142: S07 (G67 rules) on D1 bars as a separate swing setup. Plan: docs/superpowers/plans/2026-10-22-g142-s07-d1-swing.md.

D1 bars: the daily bars that h1v holds before 2018-03-19, then H1 bars grouped by server day.
Usage: g142_s07_d1.py <data dir> <out.json>
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g68_refine as h  # noqa: E402

PER = [("A 2011–2017", g.ts(2011, 1, 1), g.ts(2018, 1, 1)), ("B 2018–2021", g.ts(2018, 1, 1), g.ts(2022, 1, 1)),
       ("C 2022–06/2026", g.ts(2022, 1, 1), g.ts(2026, 7, 1)), ("sau 07/2026", g.ts(2026, 7, 1), g.ts(2030, 1, 1))]
DECIDE = PER[:3]
RUNS = 1000
INTRADAY = 1521417600            # 2018-03-19 00:00 server: first intraday bar day


def period(u):
    for n, a, z in PER:
        if a <= u < z:
            return n
    return None


def build_d1(root, out_dir):
    h1 = pd.read_csv(root / "h1v" / "XAUUSD.csv")
    old = h1[h1["time"] < INTRADAY]
    new = h1[h1["time"] >= INTRADAY].copy()
    new["day"] = new["time"] // 86400 * 86400
    agg = new.groupby("day").agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                 tickvol=("tickvol", "sum"), spread=("spread", "median")).reset_index().rename(columns={"day": "time"})
    d1 = pd.concat([old, agg], ignore_index=True).sort_values("time")
    out_dir.mkdir(parents=True, exist_ok=True)
    d1[["time", "open", "high", "low", "close", "tickvol", "spread"]].to_csv(out_dir / "XAUUSD.csv", index=False)
    return len(old), len(agg)


def use_d1(data_dir):
    g.DATA = data_dir
    g.BAR_SEC = 86400
    g._CACHE.clear()
    g.COMP_BARS, g.COOLDOWN, g.MAX_HOLD = 8, 4, 120


def run(symbol):
    D = g.load(symbol)
    sig = [(i, d) for i, d in g.signals(D) if g.block_ok(D, i, d, "B6")]
    rows = []
    for t in g.trades(symbol, "E2X", 8.0, None, sig):
        t["srv_in"], t["srv_out"] = int(D["t"][t["e0"]]), int(D["t"][t["x"]])
        t["rh"] = h.harsh(t, D)
        t["rh15"] = t["r"] - 1.5 * (t["r"] - t["rh"])
        t["p"] = period(int(D["t"][t["e0"]]))
        rows.append(t)
    return D, [t for t in rows if t["p"]]


def stat(xs):
    xs = list(xs)
    return {"n": len(xs), "mean": round(float(np.mean(xs)), 3), "total": round(float(np.sum(xs)), 1)} if xs else {"n": 0}


def main():
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    g.HERE = root.parent
    d1dir = out.parent / "d1v"
    n_old, n_new = build_d1(root, d1dir)
    use_d1(d1dir)
    D, rows = run("XAUUSD")
    res = {"nến D1": {"trước 19/03/2018 (nến D1 gốc)": n_old, "từ 19/03/2018 (gộp H1)": n_new}}
    res["theo kỳ"] = {p: stat(t["rh"] for t in rows if t["p"] == p) for p, _, _ in PER}
    res["phí×1,5"] = {p: stat(t["rh15"] for t in rows if t["p"] == p) for p, _, _ in PER}
    res["mua"] = {p: stat(t["rh"] for t in rows if t["p"] == p and t["d"] == 1) for p, _, _ in PER}
    res["bán"] = {p: stat(t["rh"] for t in rows if t["p"] == p and t["d"] == -1) for p, _, _ in PER}
    res["theo năm"] = {str(y): stat(t["rh"] for t in rows if pd.Timestamp(int(D["t"][t["e0"]]), unit="s").year == y)
                       for y in range(2011, 2027)}
    res["lệnh"] = [dict(vào=str(pd.Timestamp(int(D["t"][t["e0"]]), unit="s").date()),
                        ra=str(pd.Timestamp(int(D["t"][t["x"]]), unit="s").date()), chiều=t["d"], R=round(t["rh"], 2))
                   for t in rows]
    # random control
    dec = [t for t in rows if t["p"] in [p for p, _, _ in DECIDE]]
    actual = float(np.mean([t["rh"] for t in dec]))
    pool = {}
    for j in range(400, len(D["t"]) - 2):
        p = period(int(D["t"][j]))
        if p:
            pool.setdefault(p, []).append(j)
    rng = random.Random(142)
    hits = 0
    for _ in range(RUNS):
        u = []
        for t in dec:
            for _ in range(50):
                r = g.walk(D, rng.choice(pool[t["p"]]), t["d"], "E2X", 8.0, None)
                if r is not None:
                    r["srv_in"], r["srv_out"] = int(D["t"][r["e0"]]), int(D["t"][r["x"]])
                    u.append(h.harsh(r, D)); break
        hits += float(np.mean(u)) >= actual
    res["p ngẫu nhiên (A+B+C)"] = (hits + 1) / (RUNS + 1)
    per = res["theo kỳ"]
    ok = (all(per[p]["n"] >= 15 and per[p]["mean"] > 0 for p, _, _ in DECIDE)
          and float(np.mean([t["rh15"] for t in dec])) > 0 and res["p ngẫu nhiên (A+B+C)"] <= 0.05)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    print(json.dumps({k: res[k] for k in ("theo kỳ", "phí×1,5", "mua", "bán", "p ngẫu nhiên (A+B+C)", "kết luận")},
                     ensure_ascii=False), flush=True)
    # BTC transfer (report)
    b = pd.read_csv(root / "bars_BTCUSD_D1.csv")
    b["tickvol"] = 0
    bdir = out.parent / "btc_d1v"
    bdir.mkdir(parents=True, exist_ok=True)
    b[["time", "open", "high", "low", "close", "tickvol", "spread"]].to_csv(bdir / "BTCUSD.csv", index=False)
    use_d1(bdir)
    Db, rb = run("BTCUSD")
    res["BTCUSD D1 (chuyển giao, báo cáo)"] = {"bars": [str(pd.Timestamp(int(Db["t"][0]), unit="s").date()),
                                                       str(pd.Timestamp(int(Db["t"][-1]), unit="s").date())],
                                              "tất cả": stat(t["rh"] for t in rb), "theo kỳ": {p: stat(t["rh"] for t in rb if t["p"] == p) for p, _, _ in PER}}
    # overlap with the S07 M30 book (2018+)
    import g136_p1p4 as p1
    legs = p1.m30_book()
    xs = [t for t in rows if int(D["t"][t["e0"]]) >= INTRADAY]
    ov = [any(x["d"] == t["d"] and x["ein"] <= int(D["utc"][t["e0"]]) < x["eout"] for x in legs) for t in xs]
    res["trùng chân S07 M30 cùng chiều lúc vào (từ 2018)"] = round(float(np.mean(ov)), 3) if ov else None
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
