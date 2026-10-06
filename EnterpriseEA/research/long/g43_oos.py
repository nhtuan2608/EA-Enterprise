"""G43: out-of-sample check of the T2 candidates on symbols never used for a choice (H4 2024-02 .. 2026-10).

  python g43_oos.py

Candidates from g43_low_risk.py C1 and g43_reversal.py F (chosen on the five original symbols): initial stop
1.5 ATR instead of 2, and the momentum-close filter (signal bar or the bar before closes in the top/bottom quarter
of a range of at least 1 ATR). Also a random-entry test (same stop and exit, 2,000 runs) for stop 1.5 on the five
original symbols, which the C1 grid does not have.
"""
from __future__ import annotations

import statistics
import sys
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
from g43_low_risk import T2  # noqa: E402
from g43_reversal import arrays, has_pattern  # noqa: E402

OOS = dv.NEW + ["XAGUSD", "ETHUSD", "USOUSD", "SP500"]
for s in dv.NEW:
    replay.COMMISSION.setdefault(s, 0.009 if s.endswith("JPY") else 0.00006)


def rows_for(p, symbols, momentum=False):
    out = []
    for s in symbols:
        B = dv.load(s, "H4")
        if B is None:
            continue
        A = arrays(B["bars"])
        for t in dv.trades("T2", p, s):
            if momentum and not has_pattern("nến đà", A, t["i"], t["dir"]):
                continue
            out.append(dict(t, symbol=s))
    return out


def fmt(rs):
    if not rs:
        return "n=0"
    w = [r for r in rs if r > 0]
    l_ = [-r for r in rs if r <= 0]
    rr = statistics.fmean(w) / statistics.fmean(l_) if w and l_ else 0.0
    return f"{statistics.fmean(rs):+.3f} (RR {rr:.2f}, thắng {len(w) / len(rs):.0%}, n={len(rs)})"


def main() -> None:
    pyramid.GAP_FILL = True
    variants = {"gốc (dừng 2, trail 3)": (T2, False), "dừng 1,5": (dict(T2, stop=1.5), False),
                "lọc nến đà": (T2, True), "dừng 1,5 + nến đà": (dict(T2, stop=1.5), True)}
    lines = ["# G43: kiểm tra ngoài mẫu các ứng viên T2 (16 symbol chưa dùng để chọn, H4 2024-02..2026-10)", "",
             "| Biến thể | 12 cặp FX | XAG / ETH / dầu / SP500 | Cả 16 | 5 symbol gốc (để so) |", "|---|---|---|---|---|"]
    for name, (p, mom) in variants.items():
        fx = [t["r"] for t in rows_for(p, dv.NEW, mom)]
        tr = [t["r"] for t in rows_for(p, ["XAGUSD", "ETHUSD", "USOUSD", "SP500"], mom)]
        old = [t["r"] for t in rows_for(p, ls.SYMBOLS, mom)]
        lines.append(f"| {name} | {fmt(fx)} | {fmt(tr)} | {fmt(fx + tr)} | {fmt(old)} |")
    real_rows = rows_for(dict(T2, stop=1.5), ls.SYMBOLS)
    with Pool(12) as pool:
        sims = [v for ch in pool.map(dv.random_job, [("T2", dict(T2, stop=1.5), real_rows, 4400 + k, 200) for k in range(10)]) for v in ch]
    real = statistics.fmean(t["r"] for t in real_rows)
    lines += ["", f"Dừng 1,5 trên 5 symbol gốc: R TB {real:+.3f}, vào lệnh ngẫu nhiên TB {statistics.fmean(sims):+.3f}, "
              f"p95 {np.quantile(sims, 0.95):+.3f}, p = {float(np.mean(np.array(sims) >= real)):.4f} (2.000 lần)"]
    text = "\n".join(lines) + "\n"
    (ls.OUT / "g43_oos.md").write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
