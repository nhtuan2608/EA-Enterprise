"""G91: combine the existing setups into an FX book - select on 2010-2020, test on 2021-2025.
Pre-registered plan: docs/superpowers/plans/2026-10-11-g91-fx-portfolio.md. MT5 data only.

  python g91_fx_portfolio.py
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scorecard as sc  # noqa: E402  (G55 rows: same costs and trade management)
import filters  # noqa: E402
import pyramid  # noqa: E402

REPORT = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "reports" / "2026-10-11-g91-fx-portfolio.md"
SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY")
SETUPS = ("S02", "S04", "S06", "S06B", "S06B_USD", "T2")
PENALTY = 0.10


def mean(xs):
    return statistics.fmean(xs) if xs else 0.0


def lower90(xs, runs=3000, seed=91):
    rng = random.Random(seed)
    ms = sorted(statistics.fmean(rng.choices(xs, k=len(xs))) for _ in range(runs))
    return ms[int(0.10 * runs)]


def book(rows, risk):
    rows = sorted(rows, key=lambda r: r["utc"])
    eq = pk = 1.0
    dd = 0.0
    for r in rows:
        eq *= 1 + risk * r["r"]
        pk = max(pk, eq)
        dd = max(dd, 1 - eq / pk)
    yrs = max((rows[-1]["utc"] - rows[0]["utc"]) / (365.25 * 86400), 0.1)
    return (eq ** (1 / yrs) - 1) * 100, dd * 100


def main():
    pyramid.GAP_FILL = True
    usd, dxy = filters.usd_index(), filters.real_dxy()
    L = ["# G91: Phối hợp setup thành sổ FX — chọn trên 2010–2020, kiểm tra trên 2021–2025", "",
         "Kế hoạch: `plans/2026-10-11-g91-fx-portfolio.md`. Số liệu G55 (`scorecard.py`): chi phí thường, quản lý lệnh như EA. "
         "Ô: số lệnh / R mỗi lệnh.", "",
         "| Setup | Cặp | Train 2010–16 | Validate 2017–20 | Chọn? | Test 2021–25 |", "|---|---|---|---|---|---|"]
    chosen, all_rows = [], {}
    for setup in SETUPS:
        for s in SYMBOLS:
            rows = sc.t2_rows(s) if setup == "T2" else sc.swing_rows(setup, s, usd, dxy)
            all_rows[(setup, s)] = rows
            per = {k: [r["r"] for r in rows if r["period"] == k] for k in ("train", "validate", "test")}
            pick = (per["train"] and per["validate"] and mean(per["train"]) > 0 and mean(per["validate"]) > 0 and
                    len(per["train"]) + len(per["validate"]) >= 20)
            if pick:
                chosen.append((setup, s))
            cell = lambda k: f"{len(per[k])} / {mean(per[k]):+.3f}" if per[k] else "—"
            L.append(f"| {setup} | {s} | {cell('train')} | {cell('validate')} | {'**chọn**' if pick else ''} | {cell('test')} |")
            print(L[-1], flush=True)
    L += ["", f"Được chọn (chỉ nhìn 2010–2020): {', '.join(f'{a} {b}' for a, b in chosen) or 'không có'}.", ""]
    if chosen:
        test = [r for k in chosen for r in all_rows[k] if r["period"] == "test"]
        tr = [r["r"] for r in test]
        m, lo = mean(tr), lower90(tr)
        mp = mean([x - PENALTY for x in tr])
        checks = {"R/lệnh 2021–25 > 0": m > 0, "cận dưới bootstrap 90% > 0": lo > 0, f"sau trừ {PENALTY:.2f}R/lệnh > 0": mp > 0}
        L += [f"Sổ gộp 2021–2025: {len(tr)} lệnh, R/lệnh {m:+.3f}, cận dưới 90% {lo:+.3f}, sau trừ {PENALTY:.2f}R {mp:+.3f}."]
        L += [f"- {k}: {'đạt' if v else 'KHÔNG'}" for k, v in checks.items()]
        for risk in (0.005, 0.01):
            py, dd = book(test, risk)
            py2, dd2 = book([dict(r, r=r["r"] - PENALTY) for r in test], risk)
            L.append(f"- Rủi ro {risk:.1%}/lệnh: {py:+.1f}%/năm, DD lớn nhất {dd:.0f}% (sau trừ {PENALTY:.2f}R: {py2:+.1f}%/năm, DD {dd2:.0f}%)")
        L += ["", f"**Kết luận theo luật: {'ĐẠT' if all(checks.values()) else 'không đạt'}.**", ""]
    else:
        L += ["**Không ô nào đủ điều kiện chọn → không có sổ FX.**", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
