"""G89 curve: balance / drawdown / open-risk chart of the 10-year S07Tester simulation (like the MT5 tester graph).

  python g89_curve.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g89_full_book as m  # noqa: E402

OUT = m.REPORT.parent / "img" / "g89_curve.png"
DEPOSIT = 10_000.0
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"   # reference categorical slots 1-4


def series(variant):
    rows, legs = m.run(variant)
    rows = sorted(rows, key=lambda z: z[1])
    t = [m.START] + [r[1] for r in rows]
    eq = [1.0]
    for r, _, w in rows:
        eq.append(eq[-1] * (1 + w * r))
    eq = np.array(eq)
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1) * 100
    return np.array(t), eq * DEPOSIT, dd, legs


def open_risk(legs, t0, t1):
    days = np.arange(t0, t1, 3600 * 4)
    load = np.zeros(len(days))
    for L in legs:
        a = np.searchsorted(days, L["ein"])
        z = np.searchsorted(days, L["eout"])
        load[a:z] += m.RISK * L["w"] * 100
    return days, load


def dt(ts):
    return [datetime.fromtimestamp(int(x), timezone.utc) for x in ts]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def main():
    full = series(dict(sides=(1, -1), early=True, re=True, adds=True))
    buy = series(dict(sides=(1,), early=True, re=True, adds=True))
    core = series(dict(sides=(1,), early=False, re=False, adds=True))
    sell = series(dict(sides=(-1,), early=True, re=True, adds=True))
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=True, gridspec_kw=dict(height_ratios=[3, 2, 1.4, 1.1]))
    fig.patch.set_facecolor(SURFACE)
    curves = ((full, S1, "Đầy đủ (mua + bán, vào sớm, vào lại, bồi)"),
              (buy, S2, "Chỉ mua (vào sớm, vào lại, bồi)"),
              (core, S3, "Chỉ mua, lõi (gốc + bồi)"),
              (sell, S4, "Chỉ bán (vào sớm, vào lại, bồi)"))
    for ax in axes:
        style(ax)
    # balance, linear (like the MT5 tester) and log
    for k, (s, col, name) in enumerate(curves):
        t, bal, dd, _ = s
        x = dt(t)
        axes[0].step(x, bal, where="post", color=col, linewidth=2, label=f"{name} — cuối {bal[-1]:,.0f} USD")
        axes[1].step(x, bal, where="post", color=col, linewidth=2)
        axes[2].step(x, dd, where="post", color=col, linewidth=1.6)
    axes[0].set_title("S07 — mô phỏng 10 năm (XAUUSD, 10/2016 – 10/2026), vốn 10.000 USD, rủi ro 1,5% × trọng số, chi phí khắt khe",
                      loc="left", color=INK, fontsize=12, pad=10)
    axes[0].set_ylabel("Balance (USD)", color=INK2)
    axes[0].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axes[0].legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Balance (log)", color=INK2)
    axes[1].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    axes[1].axhline(DEPOSIT * 0.7, color="#e34948", linewidth=1, linestyle="--")
    axes[1].annotate("Sàn lỗ tổng 30% (7.000)", (dt([m.START])[0], DEPOSIT * 0.7), xytext=(4, -12),
                     textcoords="offset points", color=INK2, fontsize=8)
    axes[2].set_ylabel("Drawdown (%)", color=INK2)
    axes[2].axhline(-30, color="#e34948", linewidth=1, linestyle="--")
    days, load = open_risk(full[3], m.START, m.END)
    axes[3].fill_between(dt(days), load, step="post", color=S1, alpha=0.35, linewidth=0)
    axes[3].set_ylabel("Rủi ro mở (%)\nbản đầy đủ", color=INK2)
    axes[3].set_ylim(0, max(6.5, load.max() * 1.1))
    axes[3].xaxis.set_major_locator(mdates.YearLocator())
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.text(0.01, 0.005, "Mô phỏng Python theo quy tắc S07Tester trên dữ liệu MT5 (không phải kiểm tra ngoài mẫu). "
             "Vào sớm / vào lại / bồi M15 chỉ từ 07/2021. Balance cập nhật khi đóng lệnh.", color=INK2, fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main()
