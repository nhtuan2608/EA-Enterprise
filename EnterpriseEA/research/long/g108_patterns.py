"""G108 step 2: the readable pattern table of the structure / liquidity plans (train + validate only; the test
period 2026 stays sealed).

  python g108_patterns.py        # reads data/g108_decisions.pkl, writes the report

One plan instance = the first decision of a (direction, stop, target, server day): the same plan repeated on the
next M5 bars is counted once. Features are taken relative to the trade direction:
  sess    Asia (server h<10) / London (10-14) / New York (>=15)
  struct  M5 swings: higher highs + higher lows in the trade direction (+1), the opposite (-1), mixed (0)
  slope   12-bar M5 regression slope in the trade direction / ATR14 M30: tertiles fixed on train
  band    price vs the closed-M30 EMA21/55/100/200 band: beyond it in the trade direction (+1), inside (0), against (-1)
  m30     the forming M30 bar so far: moving with the trade (+1), against (-1), flat (0)
A cell is "stable" when train n >= 30, validate n >= 15 and the shrunk mean R (30 pseudo-trades at the
direction/period average) is > 0 in both. Control: the same count after shuffling R inside (direction, period,
session), 200 times. Day-clustered bootstrap for the lower 90% bound.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import g108_data as g

HERE = Path(__file__).resolve().parent
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-13-g108-patterns.md"
K_SHRINK, MIN_TR, MIN_VA, N_PERM, N_BOOT = 30, 30, 15, 200, 1000
KEY = ["d", "sess", "struct", "slope_b", "band", "m30"]
NAMES = {
    "d": {1: "MUA", -1: "BÁN"},
    "sess": {0: "Á", 1: "Âu", 2: "Mỹ"},
    "struct": {1: "thuận", 0: "lẫn", -1: "ngược"},
    "slope_b": {1: "dốc thuận", 0: "phẳng", -1: "dốc ngược"},
    "band": {1: "ngoài dải, thuận", 0: "trong dải", -1: "ngoài dải, ngược"},
    "m30": {1: "thuận", 0: "đứng", -1: "ngược"},
}


def usable(D: pd.DataFrame, open_test: bool = False) -> pd.DataFrame:
    """Step 2 never reads the test period unless explicitly opened."""
    return D if open_test else D[D["period"] != "test"]


def dedupe(D: pd.DataFrame) -> pd.DataFrame:
    key = (D["d"].astype(str) + "|" + D["stop"].round(6).astype(str) + "|" + D["target"].round(6).astype(str) + "|" +
           (D["time"] // 86400).astype(str))
    return D.loc[~key.duplicated()].copy()


def relative(D: pd.DataFrame) -> pd.DataFrame:
    D = D.copy()
    D["struct"] = D["d"] * D["struct"]
    D["band"] = D["d"] * D["band"]
    D["m30"] = D["d"] * D["m30_up"]
    D["slope_d"] = D["d"] * D["slope"]
    tr = D.loc[D["period"] == "train", "slope_d"].dropna()
    lo, hi = float(tr.quantile(1 / 3)), float(tr.quantile(2 / 3))
    D["slope_b"] = np.where(D["slope_d"] <= lo, -1, np.where(D["slope_d"] >= hi, 1, 0))
    D.attrs["slope_cuts"] = (lo, hi)
    return D


def boot_lower(R: np.ndarray, day: np.ndarray, q=0.10, n=N_BOOT, seed=108) -> float:
    if len(R) < 5:
        return float("nan")
    rng = np.random.default_rng(seed)
    days, inv = np.unique(day, return_inverse=True)
    s = np.bincount(inv, weights=R)
    c = np.bincount(inv)
    m = []
    for _ in range(n):
        k = rng.integers(0, len(days), len(days))
        m.append(s[k].sum() / c[k].sum())
    return float(np.quantile(m, q))


def summary(x: pd.DataFrame) -> str:
    if len(x) == 0:
        return "0 | | | |"
    return f"{len(x)} | {100 * (x['outcome'] == 1).mean():.0f}% | {x['rr'].mean():.1f} | {x['R'].mean():+.3f}"


def stable_count(P: pd.DataFrame, R: np.ndarray, base: dict) -> tuple[int, pd.DataFrame]:
    X = P[KEY + ["period"]].copy()
    X["R"] = R
    g2 = X.groupby(KEY + ["period"])["R"].agg(["sum", "count"]).unstack("period")
    g2 = g2.fillna(0.0)
    out = pd.DataFrame(index=g2.index)
    for per, mn in (("train", MIN_TR), ("validate", MIN_VA)):
        s, n = g2[("sum", per)], g2[("count", per)]
        b = np.array([base[(d, per)] for d in g2.index.get_level_values("d")])
        out[f"n_{per}"] = n
        out[f"mean_{per}"] = np.where(n > 0, s / n.replace(0, 1), np.nan)
        out[f"shr_{per}"] = (s + K_SHRINK * b) / (n + K_SHRINK)
    out["stable"] = (out["n_train"] >= MIN_TR) & (out["n_validate"] >= MIN_VA) & (out["shr_train"] > 0) & (out["shr_validate"] > 0)
    return int(out["stable"].sum()), out


def label(key: tuple) -> str:
    return " · ".join(f"{NAMES[k][v]}" if k in ("d", "sess") else f"{ {'struct': 'cấu trúc', 'slope_b': 'độ dốc', 'band': 'dải EMA', 'm30': 'nến M30'}[k]} {NAMES[k][v]}"
                      for k, v in zip(KEY, key))


def main(open_test: bool = False):
    raw = pd.read_pickle(g.OUT)
    D = relative(dedupe(usable(raw, open_test)))
    assert open_test or not (D["period"] == "test").any()
    D["day"] = D["time"] // 86400
    D["ny_hour"] = ((D["time"] % 86400) // 3600 - 7) % 24
    base = {(d, p): float(D.loc[(D["d"] == d) & (D["period"] == p), "R"].mean()) for d in (1, -1) for p in ("train", "validate")}
    L = ["# G108 bước 1–2: plan theo cấu trúc / thanh khoản trong nến M30 đang chạy — bảng mẫu lặp lại", "",
         "Ngày 13/10/2026. Plan: docs/superpowers/plans/2026-10-13-g108-m30-path-plans.md. Chỉ train (07/2024–03/2025) và "
         "validate (04/2025–12/2025); **kỳ test 2026 vẫn niêm phong**. Script: research/long/g108_data.py, g108_patterns.py, "
         "g108_audit.py.", "",
         "**Cách chấm plan:** mỗi nến M5 đóng là một quyết định; vào ở giá mở nến M5 kế tiếp. Mức sai = swing M5 gần nhất "
         "phía ngược lại (± spread). Mục tiêu = vùng thanh khoản gần nhất chưa bị lấy (đỉnh/đáy ngày trước, phiên đã xong "
         "trong 24 giờ, swing H1 trong 5 ngày). Chỉ giữ plan RR ≥ 2. Thắng = chạm mục tiêu trước (+RR); thua = phá mức sai "
         "trước, kể cả chạm cùng nến (−1); hết ngày server thì đóng ở giá cuối ngày. Có spread thật.", "",
         f"**Số plan:** {len(raw[raw['period'] != 'test'])} quyết định trên train + validate; sau khi gộp các quyết định lặp lại "
         f"cùng một plan (cùng chiều, mức sai, mục tiêu, ngày) còn **{len(D)} plan**.", "",
         "## Mức nền: vào mọi plan", "",
         "| Chiều | Kỳ | Plan | Thắng | RR TB | R/plan |", "|---|---|---|---|---|---|"]
    for d in (1, -1):
        for p in ("train", "validate"):
            L.append(f"| {NAMES['d'][d]} | {p} | {summary(D[(D['d'] == d) & (D['period'] == p)])} |")
    L += ["", "## Từng yếu tố riêng lẻ (R/plan; train → validate)", ""]
    for col, title in (("sess", "Phiên"), ("struct", "Cấu trúc M5 theo chiều lệnh"), ("slope_b", "Độ dốc M5 theo chiều lệnh"),
                       ("band", "Vị trí so với dải EMA M30"), ("m30", "Nến M30 đang chạy"), ("pos", "Nến M5 thứ mấy trong M30"),
                       ("ny_hour", "Giờ New York")):
        L += [f"### {title}", "", "| Chiều | Giá trị | Train: plan · thắng · RR · R | Validate: plan · thắng · RR · R |", "|---|---|---|---|"]
        for d in (1, -1):
            for v in sorted(D[col].dropna().unique()):
                name = NAMES.get(col, {}).get(v, str(int(v)) if col in ("pos", "ny_hour") else v)
                tr = D[(D["d"] == d) & (D[col] == v) & (D["period"] == "train")]
                va = D[(D["d"] == d) & (D[col] == v) & (D["period"] == "validate")]
                L.append(f"| {NAMES['d'][d]} | {name} | {summary(tr).replace(' | ', ' · ')} | {summary(va).replace(' | ', ' · ')} |")
        L.append("")
    n_stable, cells = stable_count(D, D["R"].to_numpy(), base)
    rng = np.random.default_rng(2026)
    perm = []
    for _ in range(N_PERM):
        R = D["R"].to_numpy().copy()
        for _, idx in D.groupby(["d", "period", "sess"]).indices.items():
            R[idx] = R[rng.permutation(idx)]
        perm.append(stable_count(D, R, base)[0])
    perm = np.array(perm)
    p_val = float((perm >= n_stable).mean())
    L += ["## Ô kết hợp (chiều × phiên × cấu trúc × độ dốc × dải EMA × nến M30)", "",
          f"Ô **ổn định** = train ≥ {MIN_TR} plan, validate ≥ {MIN_VA} plan, R/plan đã co về mức nền > 0 ở **cả hai** kỳ.", "",
          f"- Số ô có đủ mẫu ở cả hai kỳ: {int(((cells['n_train'] >= MIN_TR) & (cells['n_validate'] >= MIN_VA)).sum())}",
          f"- Số ô ổn định: **{n_stable}**",
          f"- Đối chứng xáo trộn R (200 lần): trung bình {perm.mean():.1f} ô, 95% ≤ {np.quantile(perm, 0.95):.0f} ô; "
          f"tỉ lệ lần xáo trộn có ≥ {n_stable} ô: **{p_val:.3f}**", ""]
    top = cells[cells["stable"]].copy()
    if len(top):
        top["shr_pool"] = (top["shr_train"] * top["n_train"] + top["shr_validate"] * top["n_validate"]) / (top["n_train"] + top["n_validate"])
        top = top.sort_values("shr_pool", ascending=False)
        L += ["| Ô | Train: plan · R | Validate: plan · R | Cận dưới 90% (gộp, theo ngày) |", "|---|---|---|---|"]
        for key, r in top.iterrows():
            m = np.ones(len(D), bool)
            for k, v in zip(KEY, key):
                m &= (D[k] == v).to_numpy()
            sub = D[m]
            lb = boot_lower(sub["R"].to_numpy(), sub["day"].to_numpy())
            L.append(f"| {label(key)} | {int(r['n_train'])} · {r['mean_train']:+.3f} | {int(r['n_validate'])} · "
                     f"{r['mean_validate']:+.3f} | {lb:+.3f} |")
    L.append("")
    lo, hi = D.attrs["slope_cuts"]
    L += [f"Ngưỡng độ dốc (tertile train, theo chiều lệnh, đơn vị ATR M30 mỗi nến M5): {lo:+.4f} / {hi:+.4f}.", ""]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:40]))
    print("stable", n_stable, "perm mean", perm.mean(), "p", p_val, "->", REPORT)


if __name__ == "__main__":
    main(open_test="--open-test" in sys.argv)
