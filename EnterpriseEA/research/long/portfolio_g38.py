"""G38 part 2: trend-following candidates (T1, T2, T6) next to S04 + S06B, and the portfolio for FTMO / CUSTOM.

  python portfolio_g38.py

Candidates chosen by discovery.py on 2010-2016 only:
  T1  D1 Donchian 40, stop 3 ATR, ATR trail 4
  T2  H4 Donchian 60 on the D1 EMA200 side, stop 2 ATR, ATR trail 3
  T6  D1 momentum turn (120 days), stop 3 ATR, ATR trail 3
They run as a separate profile (POSITION): they never stack with an opposite position, and one position per
symbol, side and profile (the EA rule). Checks: random entries (2,000 runs), the eight new pairs (2024-2026),
monthly correlation with S04 + S06B. Portfolios on the FTMO 1-Step account (0.3%, bootstrap of months), then
the pass odds for FTMO 1-Step and 2-Step and a CUSTOM personal account (10% trailing stop-out, no target).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import discovery as dv  # noqa: E402
import exits  # noqa: E402
import filters  # noqa: E402
import fixed_lot as fl  # noqa: E402
import ftmo2_odds as f2  # noqa: E402
import ftmo_odds as fo  # noqa: E402
import pyramid  # noqa: E402
import robustness as rb  # noqa: E402

CANDIDATES = {
    "T1": {"n": 40, "stop": 3.0, "trail": 4.0, "timeout": 120},
    "T2": {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180},
    "T6": {"n": 120, "stop": 3.0, "trail": 3.0, "timeout": 120},
}
fl.QUOTA["POSITION"] = 5
CUSTOM = {"target": 10.0, "daily": 0.05, "overall": 0.10, "trailing": True, "min_days": 0}
NEW_START = int(datetime(2024, 2, 20, tzinfo=timezone.utc).timestamp())


def account_rows(family: str, p: dict, symbols: list[str], start: int = 0) -> list[dict]:
    tf = dv.FAMILIES[family][0]
    out = []
    for s in symbols:
        B = dv.load(s, tf)
        for t in dv.trades(family, p, s, start):
            out.append({"setup": family, "profile": "POSITION", "symbol": s, "dir": t["dir"], "in": t["utc"],
                        "out": int(B["utc"][t["exit_i"]]), "dist": t["dist"], "price": t["price"], "r": t["r"],
                        "stop_atr": t["stop_atr"], "utc": t["utc"]})
    return out


def monthly(rows: list[dict]) -> dict:
    m = defaultdict(float)
    for t in rows:
        dt = datetime.fromtimestamp(t["out"], timezone.utc)
        m[(dt.year, dt.month)] += t["r"]
    return m


def corr(a: dict, b: dict) -> float:
    keys = [(y, mo) for y in range(2010, 2026) for mo in range(1, 13) if (y, mo) <= (2025, 10)]
    x, y = np.array([a.get(k, 0.0) for k in keys]), np.array([b.get(k, 0.0) for k in keys])
    return float(np.corrcoef(x, y)[0, 1])


def acc(name: str, v: dict) -> str:
    return (f"| {name} | {v['per_year']:+.2f}% | {v['dd']:.1f}% | {v['pos_years']}/{v['years']} | {v['worst_year']:+.1f}% | "
            f"{v['ann_p10']:+.2f}% / {v['ann_p50']:+.2f}% | {v['dd_p90']:.1f}% | {v['score']:.2f} |")


def main() -> None:
    pyramid.GAP_FILL = True
    rb.init_worker()
    usd, dxy = filters.usd_index(), filters.real_dxy()
    sig = {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B_USD")}
    base = (exits.account_rows(rb._C, sig["S04"], pyramid.CURRENT, None, "S04")
            + exits.account_rows(rb._C, sig["S06B_USD"], pyramid.CURRENT, 1.0, "S06B"))
    trend = {f: account_rows(f, p, ls.SYMBOLS) for f, p in CANDIDATES.items()}
    lines = ["# G38 phần 2: bám xu hướng (T1, T2, T6) cạnh S04 + S06B, danh mục cho FTMO / CUSTOM (chỉ dữ liệu MT5)", ""]

    # Checks on each candidate.
    lines += ["## 1. Kiểm chứng thêm", "",
              "| Setup | Lệnh | R TB | Ngẫu nhiên p (2.000) | 8 cặp mới 2024–2026 | Tương quan tháng với S04+S06B |", "|---|---|---|---|---|---|"]
    m_base = monthly(base)
    with Pool(12) as pool:
        for f, p in CANDIDATES.items():
            real_rows = [t for s in ls.SYMBOLS for t in dv.trades(f, p, s)]
            sims = [v for ch in pool.map(dv.random_job, [(f, p, real_rows, 900 + k, 200) for k in range(10)]) for v in ch]
            real = statistics.fmean(t["r"] for t in real_rows)
            pval = float(np.mean(np.array(sims) >= real))
            xs = [t for s in dv.NEW for t in dv.trades(f, p, s, NEW_START)]
            xs_txt = f"{statistics.fmean(t['r'] for t in xs):+.3f} (n={len(xs)})" if xs else "n=0"
            lines.append(f"| {f} {p} | {len(real_rows)} | {real:+.3f} | {pval:.3f} | {xs_txt} | {corr(monthly(trend[f]), m_base):+.2f} |")
    lines += ["", "Tương quan giữa các setup xu hướng: " + ", ".join(
        f"{a}-{b} {corr(monthly(trend[a]), monthly(trend[b])):+.2f}" for a, b in (("T1", "T2"), ("T1", "T6"), ("T2", "T6"))), ""]

    # Portfolios at 0.3% on the 1-Step account.
    rng = np.random.default_rng(38)
    portfolios = {
        "M5 S04 + S06B lọc USD + bồi (đang dùng)": base,
        "M5 + T2": base + trend["T2"],
        "M5 + T1": base + trend["T1"],
        "M5 + T6": base + trend["T6"],
        "M5 + T1 + T2": base + trend["T1"] + trend["T2"],
        "M5 + T1 + T2 + T6": base + trend["T1"] + trend["T2"] + trend["T6"],
        "Chỉ T1 + T2": trend["T1"] + trend["T2"],
    }
    lines += ["## 2. Danh mục (FTMO 1-Step, 0,3%/lệnh, 2010–2025)", "",
              "| Danh mục | %/năm | DD | Năm dương | Năm tệ nhất | Bootstrap %/năm p10 / p50 | DD p90 | Điểm |", "|---|---|---|---|---|---|---|---|"]
    summ = {}
    for name, rows in portfolios.items():
        summ[name] = rb.summary(rows, rng)
        lines.append(acc(name, summ[name]))
    best = max(summ, key=lambda k: summ[k]["score"])
    lines += ["", f"Điểm cao nhất (p10 năm / DD p90): **{best}**", ""]

    # FTMO and CUSTOM odds for the current portfolio and the best one.
    first = int(datetime(2010, 1, 4, tzinfo=timezone.utc).timestamp())
    last = int(datetime(2024, 12, 30, tzinfo=timezone.utc).timestamp())
    lines += ["## 3. FTMO và CUSTOM (lịch sử mỗi thứ Hai / xáo tháng ×3.000)", "",
              "| Danh mục | Kiểu | Rủi ro | Qua ≤ 12 tháng | ≤ 24 tháng | Trượt | Thời gian (trung vị) |", "|---|---|---|---|---|---|---|"]
    for name in dict.fromkeys(["M5 S04 + S06B lọc USD + bồi (đang dùng)", best]):
        rows = sorted(portfolios[name], key=lambda x: x["in"])
        for label, runner in (
                ("1-Step", lambda path, r, st: fo.challenge(path, r, st)),
                ("2-Step", lambda path, r, st: f2.two_step(path, r, r * 0.75, st))):
            for r in (0.005, 0.0075, 0.01):
                hist = [runner(rows, r, s) for s in range(first, last, fo.WEEK)]
                boot = fo.bootstrap(rows, r, 3000, 7, runner=runner)
                a, b = fo.summary(hist), fo.summary(boot)
                md = " / ".join(f"{x['median_days'] / 365:.1f} năm" if x["median_days"] else "-" for x in (a, b))
                lines.append(f"| {name} | {label} | {r:.2%}{' / ' + format(r * 0.75, '.2%') if label == '2-Step' else ''} | "
                             f"{a['pass_365']:.0%} / {b['pass_365']:.0%} | {a['pass_730']:.0%} / {b['pass_730']:.0%} | "
                             f"{a['fail']:.0%} / {b['fail']:.0%} | {md} |")
        for r in (0.005, 0.01):
            ys = []
            for s in range(first, last - 300 * 86400, 4 * fo.WEEK):
                path = [t for t in rows if s <= t["in"] < s + f2.YEAR]
                res = fo.challenge(path, r, s, rules=CUSTOM)
                ys.append((res["bal"] / fo.CAPITAL - 1, res["result"].startswith("FAIL")))
            rets = sorted(x for x, _ in ys)
            lines.append(f"| {name} | CUSTOM 12 tháng | {r:.2%} | lãi trung vị {statistics.median(rets):+.1%} | "
                         f"năm tệ nhất {rets[0]:+.1%} | dừng −10%: {sum(f for _, f in ys) / len(ys):.0%} | năm lỗ {sum(x < 0 for x in rets) / len(rets):.0%} |")
    text = "\n".join(lines) + "\n"
    (ls.OUT / "portfolio_g38.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
