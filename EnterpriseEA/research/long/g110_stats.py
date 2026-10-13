"""G110 step 2: does tick volume vs price tell a holding break from a failing one? Train + validate only.

  python g110_stats.py XAUUSD EURUSD GBPUSD USDJPY     # writes docs/superpowers/reports/2026-10-13-g110-volume.md

For each volume feature: tertiles fixed on train (real levels Z + G); hold rate, follow (S2) and fade (F) R by
tertile, train and validate. "Fake push" = effort (body / relative volume) in the top tertile and relative break
volume in the bottom tertile. Divergence = price over 12 bars and the 12-bar close-location delta disagree.
Shuffle test: top-minus-bottom tertile hold-rate difference vs 1000 shuffles of hold inside (type, period).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g8
from g109_setups import SUF

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / f"2026-10-13-g110-volume{SUF}.md"
VOL = ["tv_break", "tv_appr", "tv_slope", "effort", "delta6", "delta12", "wick", "body",
       "compress", "expand", "void_ahead", "zone_ahead", "bos_dist", "pole", "cons_slope", "wedge_conv", "pa_close"]
FLAGS = [("push", "đẩy láo (giá đi xa, volume thấp)"), ("diverg", "phân kỳ giá / delta 12 nến"), ("nr7", "NR7 trước phá (nén)"),
         ("bos_h1", "phá luôn swing H1 (phá cấu trúc)"), ("flag_pat", "mẫu cờ, phá theo cột cờ"),
         ("wedge_with", "nêm, phá đúng chiều kinh điển"), ("void_near", "có FVG chưa lấp ≤ 1 ATR phía trước"),
         ("struct_up", "cấu trúc swing M5 thuận chiều phá")]
NAMES = {"tv_break": "volume 2 nến phá (tương đối)", "tv_appr": "volume 6 nến tiếp cận", "tv_slope": "độ dốc volume trước phá",
         "effort": "kết quả / volume (đẩy láo khi cao)", "delta6": "delta giả 6 nến (theo chiều phá)",
         "delta12": "delta giả 12 nến (theo chiều phá)", "wick": "râu nến phá theo chiều phá", "body": "thân 2 nến phá / ATR M5",
         "compress": "PA: biên 12 nến trước phá (nén)", "expand": "PA: độ bung của nến phá", "void_ahead": "PA: khoảng tới FVG phía trước",
         "zone_ahead": "PA: khoảng tới vùng cản phía trước", "bos_dist": "PA: vượt swing H1 (ATR)", "pole": "PA: cột cờ (đà trước)",
         "cons_slope": "PA: độ dốc vùng tích lũy", "wedge_conv": "PA: độ hội tụ nêm", "pa_close": "PA: giá đóng nến phá trong biên"}


def tertiles(E: pd.DataFrame, col: str):
    tr = E.loc[(E["period"] == "train") & E["type"].isin(["Z", "G"]), col].dropna()
    return float(tr.quantile(1 / 3)), float(tr.quantile(2 / 3))


def bucket(x: pd.Series, cuts) -> pd.Series:
    lo, hi = cuts
    return pd.Series(np.where(x.isna(), np.nan, np.where(x <= lo, 0, np.where(x >= hi, 2, 1))), index=x.index)


def cell(x: pd.DataFrame) -> str:
    if len(x) < 20:
        return f"{len(x)} | | |"
    fo = x["fo_Ra"].dropna(); fa = x["fa_Ra"].dropna()
    return (f"{len(x)} | {100 * x['hold'].mean():.0f}% | {fo.mean():+.3f} ({len(fo)}) | {fa.mean():+.3f} ({len(fa)})")


def shuffle_p(E: pd.DataFrame, b: pd.Series, n=1000, seed=110):
    """Observed top - bottom hold difference per period and the share of shuffles at least as large (two-sided)."""
    rng = np.random.default_rng(seed)
    out = {}
    for per in ("train", "validate"):
        m = (E["period"] == per) & b.notna()
        y = E.loc[m, "hold"].to_numpy(float); g = b[m].to_numpy()
        obs = y[g == 2].mean() - y[g == 0].mean()
        cnt = 0
        for _ in range(n):
            ys = rng.permutation(y)
            cnt += abs(ys[g == 2].mean() - ys[g == 0].mean()) >= abs(obs)
        out[per] = (obs, cnt / n)
    return out


def section(sym: str) -> list[str]:
    E = pd.read_pickle(g8.DATA / f"g110_events_{sym}{SUF}.pkl")
    assert not (E["period"] == "test").any()
    L = [f"## {sym}", "", f"Sự kiện phá (train + validate): {len(E)} — vùng thật Z {int((E['type'] == 'Z').sum())}, "
         f"swing M5 G {int((E['type'] == 'G').sum())}, vùng giả F {int((E['type'] == 'F').sum())}.", "",
         "### Mức nền", "", "| Loại mức | Kỳ | Sự kiện | Giữ | Theo (S2) R/lệnh (số lệnh) | Ngược (F) R/lệnh (số lệnh) | Ngẫu nhiên: theo / ngược |",
         "|---|---|---|---|---|---|---|"]
    for typ in ("Z", "G", "F"):
        for per in ("train", "validate"):
            x = E[(E["type"] == typ) & (E["period"] == per)]
            L.append(f"| {typ} | {per} | {cell(x)} | {x['fo_rand'].mean():+.3f} / {x['fa_rand'].mean():+.3f} |")
    R = E[E["type"].isin(["Z", "G"])].copy()
    L += ["", "### Từng đặc trưng volume (mức thật Z + G): sự kiện · giữ · theo R (lệnh) · ngược R (lệnh)", "",
          "| Đặc trưng | Nhóm | Train | Validate |", "|---|---|---|---|"]
    tests = []
    for col in VOL:
        cuts = tertiles(E, col)
        b = bucket(R[col], cuts)
        for k, nm in ((0, "thấp"), (1, "giữa"), (2, "cao")):
            L.append(f"| {NAMES[col]} | {nm} | {cell(R[(b == k) & (R['period'] == 'train')])} | {cell(R[(b == k) & (R['period'] == 'validate')])} |")
        tests.append((col, shuffle_p(R, b)))
    R["push"] = ((bucket(R["effort"], tertiles(E, "effort")) == 2) & (bucket(R["tv_break"], tertiles(E, "tv_break")) == 0)).astype(int)
    R["void_near"] = (R["void_ahead"] <= 1.0).astype(int)
    R["struct_up"] = (R["struct_m5"] == 1).astype(int)
    R["wedge_with"] = (R["wedge_with"] == 1).astype(int)
    L += ["", "### Cờ volume và price action (mức thật Z + G)", "", "| Cờ | Giá trị | Train | Validate |", "|---|---|---|---|"]
    for col, nm in FLAGS:
        for v in (1, 0):
            L.append(f"| {nm} | {'có' if v else 'không'} | {cell(R[(R[col] == v) & (R['period'] == 'train')])} | "
                     f"{cell(R[(R[col] == v) & (R['period'] == 'validate')])} |")
    for col, nm in FLAGS:
        b = pd.Series(np.where(R[col].isna(), np.nan, np.where(R[col] == 1, 2, 0)), index=R.index)
        tests.append((col, shuffle_p(R, b)))
        NAMES[col] = "cờ: " + nm
    L += ["", "### Kiểm định xáo trộn: tỉ lệ giữ nhóm cao (hoặc có cờ) − nhóm thấp (không cờ), điểm %, p hai phía", "",
          "| Đặc trưng | Train: chênh · p | Validate: chênh · p | Cùng dấu và p < 0,05 ở cả hai? |", "|---|---|---|---|"]
    for col, res in tests:
        (d1, p1), (d2, p2) = res["train"], res["validate"]
        ok = "**có**" if (np.sign(d1) == np.sign(d2) and p1 < 0.05 and p2 < 0.05) else "không"
        L.append(f"| {NAMES[col]} | {100 * d1:+.1f} · {p1:.3f} | {100 * d2:+.1f} · {p2:.3f} | {ok} |")
    L.append("")
    return L


def main(symbols):
    L = ["# G110 bước 1–2: volume từng nến và volume cộng dồn so với giá — phá thật hay phá giả", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g110-break-quality-volume.md. Dữ liệu raw MT5 có tick volume "
         "(EURUSD/GBPUSD đã đổi sang giờ server). Chỉ train 07/2024–03/2025 và validate 04–12/2025 (FX tới 10/2025); "
         "**test 2026 niêm phong**. Script: research/long/g110_breaks.py, g110_stats.py, g110_audit.py.", "",
         "Sự kiện phá = lần đầu 2 nến M5 đóng bên kia mép mức. Giữ = 6 nến sau không có nến nào đóng quay lại. Theo (S2) = limit "
         "tại mép, stop phía bên kia mức; ngược (F) = sau khi đóng quay lại, vào ngược, stop sau cực trị cú phá. Cả hai mục tiêu 2R, "
         "spread thật, tối đa 4 giờ, stop ≥ 8 spread. Volume tương đối = tick volume / trung vị cùng phút 20 ngày trước.", ""]
    for s in symbols:
        L += section(s)
        print(s, "done", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", REPORT)


if __name__ == "__main__":
    main(sys.argv[1:] or ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"])
