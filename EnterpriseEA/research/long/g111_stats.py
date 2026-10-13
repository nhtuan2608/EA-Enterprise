"""G111 step 2: retracement depth vs Fibonacci, and reversal trades at tested levels (Fibonacci vs fake ratios, zones
vs fake zones, confluence, volume dry-up, divergence). Train + validate only.

  python g111_stats.py XAUUSD EURUSD GBPUSD USDJPY      # writes docs/superpowers/reports/2026-10-13-g111-step2.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g109_setups import SUF
from g108_patterns import boot_lower

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g111-step2{SUF}.md"
FIB = (0.236, 0.382, 0.5, 0.618, 0.786)
FAKE = (0.30, 0.45, 0.55, 0.70)


def stat(x: pd.DataFrame, col="Ra") -> str:
    v = x[col].dropna()
    if len(v) < 15:
        return f"{len(v)} | | |"
    return f"{len(v)} | {100 * (v > 0).mean():.0f}% | {v.mean():+.3f} | {boot_lower(v.to_numpy(), x.loc[v.index, 'day'].to_numpy()):+.3f}"


def perm_diff(a: np.ndarray, b: np.ndarray, n=2000, seed=111):
    rng = np.random.default_rng(seed)
    obs = a.mean() - b.mean()
    allv = np.r_[a, b]
    cnt = 0
    for _ in range(n):
        p = rng.permutation(allv)
        cnt += abs(p[:len(a)].mean() - p[len(a):].mean()) >= abs(obs)
    return obs, cnt / n


def section(sym: str) -> list[str]:
    LV = pd.read_pickle(g8.DATA / f"g111_levels_{sym}{SUF}.pkl")
    T = pd.read_pickle(g8.DATA / f"g111_tests_{sym}{SUF}.pkl")
    assert not (T["period"] == "test").any() and not (LV["period"] == "test").any()
    L = [f"## {sym}", "", "### A. Hôm nay thoái lui sâu tới đâu trong biên ngày trước (đo từ cuối nhịp ngày trước)", "",
         "| Kỳ | Ngày | Thoái lui < 23,6% | 23,6–50% | 50–78,6% | 78,6–100% | vượt qua đầu kia (>100%) | Gần một tỉ lệ Fibo (±2%) | Gần một tỉ lệ giả (±2%) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for per in ("train", "validate"):
        x = LV[LV["period"] == per]["depth"].dropna()
        near_f = np.mean([any(abs(v - r) <= 0.02 for r in FIB) for v in x])
        near_k = np.mean([any(abs(v - r) <= 0.02 for r in FAKE) for v in x])
        bins = [(x < 0.236).mean(), ((x >= 0.236) & (x < 0.5)).mean(), ((x >= 0.5) & (x < 0.786)).mean(), ((x >= 0.786) & (x <= 1)).mean(), (x > 1).mean()]
        L.append(f"| {per} | {len(x)} | " + " | ".join(f"{100 * b:.0f}%" for b in bins) +
                 f" | {100 * near_f:.1f}% (5 tỉ lệ → {100 * near_f / 5:.1f}%/tỉ lệ) | {100 * near_k:.1f}% (4 tỉ lệ → {100 * near_k / 4:.1f}%/tỉ lệ) |")
    L += ["", "### B. Lệnh đảo chiều khi giá test mức (chạm, không đóng vượt): lệnh · thắng · R/lệnh · cận dưới 90% (theo lệnh)", "",
          "| Nhóm mức | Train | Validate | Ngẫu nhiên (validate) |", "|---|---|---|---|"]
    for fam in ("PFIB", "PFAKE", "AFIB", "AFAKE", "DFIB", "DFAKE", "ZONE", "ZFAKE"):
        x = T[T["fam"] == fam]
        L.append(f"| {fam} | {stat(x[x['period'] == 'train'])} | {stat(x[x['period'] == 'validate'])} | {x.loc[x['period'] == 'validate', 'Rrand'].mean():+.3f} |")
    L += ["", "Fibonacci so với Fibonacci giả (gộp P + A + D), kiểm định hoán vị trên R/lệnh:", ""]
    for per in ("train", "validate"):
        a = T[(T["period"] == per) & T["fam"].str.endswith("FIB")]["Ra"].to_numpy()
        b = T[(T["period"] == per) & T["fam"].str.endswith("FAKE") & (T["fam"] != "ZFAKE")]["Ra"].to_numpy()
        if len(a) > 10 and len(b) > 10:
            d, p = perm_diff(a, b)
            L.append(f"- {per}: Fibonacci {a.mean():+.3f} ({len(a)}) so với giả {b.mean():+.3f} ({len(b)}): chênh {d:+.3f}, p = {p:.3f}")
    L += ["", "### Theo từng tỉ lệ (P + A + D gộp)", "", "| Tỉ lệ | Fibonacci? | Train | Validate |", "|---|---|---|---|"]
    F = T[T["fam"].isin(["PFIB", "PFAKE", "AFIB", "AFAKE", "DFIB", "DFAKE"])]
    for r in sorted(F["ratio"].unique()):
        x = F[np.isclose(F["ratio"], r)]
        L.append(f"| {100 * r:.1f}% | {'có' if any(np.isclose(r, f) for f in FIB) else 'giả'} | {stat(x[x['period'] == 'train'])} | {stat(x[x['period'] == 'validate'])} |")
    R = T[~T["fake"]].copy()
    R["conf_b"] = np.where(R["conf"] >= 2, "≥ 2 mức khác", np.where(R["conf"] == 1, "1 mức khác", "đứng riêng"))
    q = R.loc[R["period"] == "train", "rv6"].quantile([1 / 3, 2 / 3]).to_numpy()
    R["dry"] = np.where(R["rv6"] <= q[0], "cạn (volume thấp)", np.where(R["rv6"] >= q[1], "volume cao", "giữa"))
    R["slope_b"] = np.where(R["rv_slope"] < 0, "volume giảm dần", "volume tăng dần")
    R["div_b"] = np.where(R["diverg"] == 1, "có phân kỳ giá–delta", "không phân kỳ")
    R["dir_b"] = np.where(R["d"] == 1, "MUA (test đáy)", "BÁN (test đỉnh)")
    R["fz"] = np.where(R["fam"] == "ZONE", "vùng thật", "Fibonacci")
    L += ["", "### Mức thật: theo hợp lưu, cạn volume, phân kỳ, chiều", "", "| Nhóm | Giá trị | Train | Validate |", "|---|---|---|---|"]
    for col, nm in (("conf_b", "hợp lưu"), ("dry", "volume 6 nến tiếp cận"), ("slope_b", "xu hướng volume"), ("div_b", "phân kỳ"),
                    ("dir_b", "chiều"), ("fz", "loại")):
        for v in sorted(R[col].unique()):
            x = R[R[col] == v]
            L.append(f"| {nm} | {v} | {stat(x[x['period'] == 'train'])} | {stat(x[x['period'] == 'validate'])} |")
    L += ["", "Kiểm định hoán vị (mức thật): cạn volume so với volume cao; có phân kỳ so với không:", ""]
    for per in ("train", "validate"):
        x = R[R["period"] == per]
        for col, va, vb in (("dry", "cạn (volume thấp)", "volume cao"), ("div_b", "có phân kỳ giá–delta", "không phân kỳ")):
            a = x[x[col] == va]["Ra"].to_numpy(); b = x[x[col] == vb]["Ra"].to_numpy()
            if len(a) > 10 and len(b) > 10:
                d, p = perm_diff(a, b)
                L.append(f"- {per}, {va} − {vb}: {d:+.3f} R/lệnh, p = {p:.3f}")
    L.append("")
    return L


def main(symbols):
    L = ["# G111 bước 1–2: thoái lui, Fibonacci và test vùng (đảo chiều khi giá chạm mức mà không phá)", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g111-retrace-fib-tests.md. Dữ liệu raw MT5 (EURUSD/GBPUSD đã đổi "
         "sang giờ server). Chỉ train 07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); **test 2026 niêm phong**. "
         "Script: research/long/g111_levels.py, g111_stats.py, g111_audit.py.", "",
         "Lệnh đảo chiều T: limit đặt sẵn ở mép gần của mức; stop = mép xa + 0,5 w + spread; mục tiêu 2R; nến khớp chỉ xét stop; "
         "tối đa 4 giờ; stop ≥ 8 spread. Đặc trưng chỉ dùng nến trước nến chạm. Fibonacci giả = tỉ lệ 30/45/55/70%.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
