"""G43 part E2: SCALP only while a T2 position (H4 trend, the verified edge) is open on the same side. MT5 data only.

  python g43_scalp_gated.py

Same families, sets, periods, costs and controls as g43_scalp.py; a signal is kept only when its bar falls inside a
T2 trade (H4 Donchian 60, D1 EMA200 side, stop 2 ATR, trail 3) on the same symbol and side. Chosen on
2021-10 .. 2023-06 only; out-of-sample on the 16 other symbols.
"""
from __future__ import annotations

import statistics
import sys
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import g43_scalp as sc  # noqa: E402
import pyramid  # noqa: E402
from g43_low_risk import T2  # noqa: E402

_GATE: dict = {}


def gate(symbol: str):
    if symbol not in _GATE:
        B = dv.load(symbol, "H4")
        iv = []
        if B is not None:
            for t in dv.trades("T2", T2, symbol):
                iv.append((t["utc"], int(B["utc"][min(t["exit_i"], len(B["utc"]) - 1)]), t["dir"]))
        _GATE[symbol] = iv
    return _GATE[symbol]


def inside(symbol, utc, d):
    return any(a < utc <= b and dd == d for a, b, dd in gate(symbol))


def gated(fam, p, symbol, start=0):
    return [t for t in sc.trades(fam, p, symbol, start) if inside(symbol, t["utc"], t["dir"])]


def scan_job(job):
    fam, p = job
    pyramid.GAP_FILL = True
    rows = [t for s in sc.SYMBOLS for t in gated(fam, p, s)]
    by = {k: sc.stats([t["r"] for t in rows if sc.period(t["utc"]) == k]) for k in ("train", "validate", "test")}
    return {"fam": fam, "p": p, **by, "rows": rows}


def main() -> None:
    pyramid.GAP_FILL = True
    lines = ["# G43 phần E2: SCALP chỉ khi T2 đang mở cùng chiều (chỉ dữ liệu MT5)", "",
             "| Họ | Bộ dương cả 3 kỳ | Bộ chọn | Train | Validate | Test | Ngẫu nhiên p | Phí ×2 + 0,1R | Ngoài mẫu 16 symbol |",
             "|---|---|---|---|---|---|---|---|---|"]
    jobs = [(f, p) for f, (_, g) in sc.FAMILIES.items() for p in g]
    with Pool(12) as pool:
        res = pool.map(scan_job, jobs)
        for f in sc.FAMILIES:
            rs = [r for r in res if r["fam"] == f]
            pos = sum(1 for r in rs if all(r[k]["exp"] > 0 and r[k]["n"] > 0 for k in ("train", "validate", "test")))
            cand = [r for r in rs if r["train"]["n"] >= 40] or rs
            b = max(cand, key=lambda r: r["train"]["exp"])
            rows = b["rows"]
            if not rows:
                lines.append(f"| {f} | {pos}/{len(rs)} | {b['p']} | n=0 | | | | | |")
                continue
            real = statistics.fmean(t["r"] for t in rows)
            sims = [v for ch in pool.map(sc.random_job, [(f, b["p"], rows, 4500 + k, 30) for k in range(10)]) for v in ch]
            p_rand = float(np.mean(np.array(sims) >= real))
            fee = []
            for t in rows:
                B = dv.load(t["symbol"], sc.TF)
                risk = t["stop_atr"] * B["atr"][t["i"]]
                fee.append(t["r"] - sc.replay.COMMISSION.get(t["symbol"], 0.0) / max(risk, 1e-12) - 0.1)
            oos = [t["r"] for s in sc.OOS for t in gated(f, b["p"], s, sc.OOS_START)]
            lines.append(f"| {f} | {pos}/{len(rs)} | {b['p']} | {sc.fmt(b['train'])} | {sc.fmt(b['validate'])} | "
                         f"{sc.fmt(b['test'])} | {p_rand:.3f} | {statistics.fmean(fee):+.3f} | {sc.fmt(sc.stats(oos))} |")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g43_scalp_gated.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
