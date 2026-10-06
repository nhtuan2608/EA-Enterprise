"""G47: Fibonacci OTE (G45 Z5) with trend exits, by asset class and on H4. Pre-registered plan:
docs/superpowers/plans/2026-10-07-g47-fib-ote.md. MT5 data only.

  python g47_fib.py

Grid (24 sets, D1 EMA200 trend filter always on): timeframe {H1, H4} x entry {61.8%, 70.5%} x leg {3, 5 ATR}
x exit {2R, 3R, ATR trail 3}. Orders, fills and costs as g45_zones.py (limit at the Fibonacci level, stop below
the swing, a fill bar that also reaches the stop is a full loss). Chosen on 2010-2016 (best expectancy, >= 60
train trades); checks: validate and test positive, random entries p < 0.05/24, neighbours >= 60%, commission
x2 + 0.1R, 16 out-of-sample symbols split FX / trend assets, and the G4 portfolio with and without it.
"""
from __future__ import annotations

import itertools
import statistics
import sys
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import g45_zones as gz  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402

GRID = [dict(zip(("tf", "fib", "leg", "target"), v)) for v in itertools.product(
    ("H1", "H4"), (0.618, 0.705), (3.0, 5.0), ("R2", "R3", "trail"))]
FX_OOS = dv.NEW
TREND_OOS = ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
ALPHA = 0.05 / len(GRID)


def params(p):
    return {"leg": p["leg"], "fib": p["fib"], "trend": True, "target": p["target"]}


def trades(p, symbol, start=0):
    gz.TF = p["tf"]
    return gz.trades("Z5", params(p), symbol, start)


def scan_job(p):
    pyramid.GAP_FILL = True
    rows = [t for s in ls.SYMBOLS for t in trades(p, s)]
    by = {k: gz.stats([t["r"] for t in rows if gz.period(t["utc"]) == k]) for k in ("train", "validate", "test")}
    return {"p": p, **by, "rows": rows}


def random_job(job):
    p, rows, seed, runs = job
    gz.TF = p["tf"]
    return gz.random_job(("Z5", params(p), rows, seed, runs))


def neighbours(p, res):
    near = [r for r in res if sum(r["p"][k] != p[k] for k in p) == 1]
    ok = [r for r in near if all(r[k]["exp"] > 0 for k in ("train", "validate", "test"))]
    return len(ok), len(near)


def main():
    pyramid.GAP_FILL = True
    lines = ["# G47: Fibonacci OTE — kết quả (chỉ dữ liệu MT5, kế hoạch đăng ký trước)", "",
             "## 1. Lưới 24 bộ (lọc xu hướng D1 luôn bật)", "",
             "| Khung | Mức | Chân sóng | Thoát | Train | Validate | Test | Dương 3 kỳ |", "|---|---|---|---|---|---|---|---|"]
    with Pool(12) as pool:
        res = pool.map(scan_job, GRID)
        for r in res:
            p = r["p"]
            pos = all(r[k]["exp"] > 0 and r[k]["n"] > 0 for k in ("train", "validate", "test"))
            lines.append(f"| {p['tf']} | {p['fib']} | {p['leg']:g} | {p['target']} | {gz.fmt(r['train'])} | "
                         f"{gz.fmt(r['validate'])} | {gz.fmt(r['test'])} | {'có' if pos else ''} |")
        cand = [r for r in res if r["train"]["n"] >= 60]
        best = max(cand, key=lambda r: r["train"]["exp"])
        p, rows = best["p"], best["rows"]
        real = statistics.fmean(t["r"] for t in rows)
        sims = [v for ch in pool.map(random_job, [(p, rows, 4700 + k, 30) for k in range(10)]) for v in ch]
        p_rand = float(np.mean(np.array(sims) >= real))
    nb_ok, nb_n = neighbours(p, res)
    gz.TF = p["tf"]
    fee = []
    for t in rows:
        B = dv.load(t["symbol"], p["tf"])
        risk = t["stop_atr"] * B["atr"][t["i"]]
        fee.append(t["r"] - replay.COMMISSION.get(t["symbol"], 0.0) / max(risk, 1e-12) - 0.1)
    fx = [t["r"] for s in FX_OOS for t in trades(p, s, gz.OOS_START)]
    tr = [t["r"] for s in TREND_OOS for t in trades(p, s, gz.OOS_START)]
    per_sym = ", ".join(f"{s} {statistics.fmean([t['r'] for t in rows if t['symbol'] == s]):+.2f}"
                        for s in ls.SYMBOLS if any(t["symbol"] == s for t in rows))
    checks = {
        "dương validate và test": best["validate"]["exp"] > 0 and best["test"]["exp"] > 0,
        f"ngẫu nhiên p < {ALPHA:.4f}": p_rand < ALPHA,
        "láng giềng ≥ 60%": nb_n > 0 and nb_ok / nb_n >= 0.6,
        "phí ×2 + 0,1R > 0": statistics.fmean(fee) > 0,
        "ngoài mẫu không âm": gz.stats(fx + tr)["exp"] >= 0,
    }
    lines += ["", f"## 2. Bộ chọn (train): {p}", "",
              f"- Train / validate / test: {gz.fmt(best['train'])} / {gz.fmt(best['validate'])} / {gz.fmt(best['test'])}",
              f"- Vào lệnh ngẫu nhiên: TB {statistics.fmean(sims):+.3f}, p = {p_rand:.4f}",
              f"- Láng giềng dương 3 kỳ: {nb_ok}/{nb_n}",
              f"- Phí ×2 + trượt 0,1R: {statistics.fmean(fee):+.3f}",
              f"- Ngoài mẫu FX 12 cặp: {gz.fmt(gz.stats(fx))}; tài sản xu hướng 4: {gz.fmt(gz.stats(tr))}",
              f"- Theo symbol (2010–2025): {per_sym}", "",
              "| Tiêu chí | Đạt |", "|---|---|", *[f"| {k} | {'có' if v else '**không**'} |" for k, v in checks.items()], ""]
    passed = all(checks.values())
    if passed:
        import g43_final as gf
        import g43_low_risk as g
        base = g.base_rows()
        t2 = gf.t2_variant(True, 1.0)
        z5 = []
        for t in rows:
            B = dv.load(t["symbol"], p["tf"])
            z5.append({"setup": "Z5", "profile": "SWING", "symbol": t["symbol"], "dir": t["dir"], "in": t["utc"],
                       "out": int(B["utc"][min(t["exit_i"], len(B["utc"]) - 1)]), "dist": 1.0, "price": 1.0, "r": t["r"]})
        lines += ["## 3. Danh mục G4 có / không Z5", "", *g.HEAD]
        for name, rws in (("G4", base + t2), ("G4 + Z5", base + t2 + z5)):
            w, mult = gf.weighted(rws)
            lines += g.table(f"{name} ({', '.join(f'{k} {v:.2f}' for k, v in sorted(w.items()))})", g.by_period(rws, mult=mult))
    lines.append(f"**Kết luận: {'đạt mọi tiêu chí' if passed else 'không đạt'}**")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g47_fib.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
