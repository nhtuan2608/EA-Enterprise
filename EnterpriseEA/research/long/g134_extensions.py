"""G134: four extensions - D1 golden/death cross weight for S07, S07 on H1 as a separate bot, the V-reversal M30
candidate (G118 A) reproduced and run forward, CtxBox forward. Plan: docs/superpowers/plans/2026-10-21-g134-four-extensions.md.
MT5 data only; the terminal is read only (MetaTrader5 copy_rates_from_pos), nothing is sent to it.

  python g134_extensions.py
"""
from __future__ import annotations

import io
import statistics
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPORT = HERE.parents[1] / "docs" / "superpowers" / "reports" / "2026-10-21-g134-four-extensions.md"
CAP0, YEAR = 10_000.0, 365.25 * 86400
TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def ts(s):
    return int(pd.Timestamp(s).timestamp())


def mean(x):
    return statistics.fmean(x) if x else 0.0


def sim(legs, a, b):
    """legs: dict(t_in, t_out, r, risk) (risk as a fraction). Compounded on closed equity. -> (cagr, dd, mar, n)."""
    sel = [x for x in legs if a <= x["t_in"] < b and x["risk"] > 0]
    if not sel:
        return 0.0, 0.0, 0.0, 0
    ev = sorted([(x["t_in"], 1, k) for k, x in enumerate(sel)] + [(x["t_out"], 0, k) for k, x in enumerate(sel)])
    E = pk = CAP0
    dd, money = 0.0, {}
    for t, kind, k in ev:
        if kind == 1:
            money[k] = E * sel[k]["risk"]
        elif k in money:
            E += money.pop(k) * sel[k]["r"]
            pk = max(pk, E)
            dd = max(dd, 1 - E / pk)
    yrs = max((b - a) / YEAR, 0.1)
    cagr = (E / CAP0) ** (1 / yrs) - 1 if E > 0 else -1.0
    return cagr, dd, (cagr / dd if dd > 0 else float("inf")), len(sel)


def fmt(s):
    return f"{s[0]:+.1%} / {s[1]:.1%} / **{s[2]:.2f}** / {s[3]}"


# ---------------------------------------------------------------------------
def s07_legs():
    import g107_portfolio as p107
    import g67_dmi_ema as g67
    out = []
    for L in p107.s07_legs():
        u_in = int((L["t_in"] - pd.Timestamp(0)).total_seconds())
        u_out = int((L["t_out"] - pd.Timestamp(0)).total_seconds())
        off = lambda u: 10800 if g67.us_dst(u) else 7200
        out.append(dict(d=int(L["d"]), u_in=u_in, u_out=u_out, s_in=u_in + off(u_in), r=float(L["r"]),
                        w=float(L["money"]) / (CAP0 * 0.015)))
    return out


def d1_state():
    m = pd.read_csv(HERE / "data" / "m30v" / "XAUUSD.csv")
    D = m.assign(day=m["time"] // 86400).groupby("day")["close"].last()
    s50, s200 = D.rolling(50).mean(), D.rolling(200).mean()
    return dict(zip(D.index.to_numpy(), np.sign((s50 - s200).fillna(0).to_numpy())))


def part1(L, legs):
    st = d1_state()
    days = np.array(sorted(st))
    for x in legs:
        k = np.searchsorted(days, x["s_in"] // 86400, side="left") - 1      # last completed server day
        x["aligned"] = k >= 0 and st[days[k]] == x["d"]
    per = [("Train 03/2018–2021", ts("2018-03-05"), ts("2022-01-01")), ("Validate 2022–2025", ts("2022-01-01"), ts("2026-01-01")),
           ("2026", ts("2026-01-01"), ts("2026-10-10"))]
    L += ["## 1. Trọng số golden / death cross D1 cho S07", "",
          "Sổ S07 (G89/G107), 1,5% × trọng số EA, lãi kép, vốn 10.000. Ô: %/năm / DD / **MAR** / số chân. Thời gian theo server.", "",
          "| Lệnh ngược trạng thái D1 | " + " | ".join(p for p, _, _ in per) + " |", "|---|---|---|---|"]
    res = {}
    for name, wmul in (("× 1,0 (gốc)", 1.0), ("× 0,5", 0.5), ("bỏ (× 0)", 0.0)):
        L_ = [dict(t_in=x["s_in"], t_out=x["s_in"] + (x["u_out"] - x["u_in"]), r=x["r"],
                   risk=0.015 * x["w"] * (1.0 if x["aligned"] else wmul)) for x in legs]
        res[wmul] = [sim(L_, a, b) for _, a, b in per]
        L.append(f"| {name} | " + " | ".join(fmt(s) for s in res[wmul]) + " |")
    share = mean([1.0 if x["aligned"] else 0.0 for x in legs if x["s_in"] >= ts("2018-03-05")])
    keep05 = all(res[0.5][k][2] >= res[1.0][k][2] for k in range(3))
    L += ["", f"Chân cùng trạng thái D1: {share:.0%}. Theo kế hoạch chọn trước × 0,5; "
              f"{'giữ × 0,5 (MAR không thấp hơn gốc ở kỳ nào)' if keep05 else 'MAR × 0,5 thấp hơn gốc ở ít nhất một kỳ → xem × 0'}.", ""]
    return res


def part2(L, legs):
    import g67_dmi_ema as g
    import g67_timeframes as gt
    rows = gt.run("H1", 4, 2, 120)
    labels = ("pre", "train", "validate", "test", "examples")
    names = {"pre": "09/2018–07/2021 (chưa dùng)", "train": "Train 07/2021–2023", "validate": "Validate 2024–06/2025",
             "test": "Test 07/2025–06/2026", "examples": "07/2026+"}
    L += ["## 2. S07 khung H1 như một bot riêng", "",
          "Luật G67 cuối trên H1, cửa sổ nén 4 nến (4 giờ), nghỉ 2 nến, giữ tối đa 120 nến, TP 8R, chi phí khắt khe. "
          "R/lệnh theo SL ban đầu.", "", "| Kỳ | Lệnh | R/lệnh | Mua | Bán |", "|---|---|---|---|---|"]
    for p in labels:
        seg = [t for t in rows if t["p"] == p]
        b = [t["r"] for t in seg if t["d"] == 1]
        s = [t["r"] for t in seg if t["d"] == -1]
        L.append(f"| {names[p]} | {len(seg)} | {mean([t['r'] for t in seg]):+.3f} | {len(b)} / {mean(b):+.3f} | {len(s)} / {mean(s):+.3f} |")
    # overlap with the M30 legs (UTC on both sides)
    ov = 0
    for t in rows:
        a, z = t["utc"], t["utc"] + t["hold_h"] * 3600
        if any(x["d"] == t["d"] and x["u_in"] < z and x["u_out"] > a for x in legs):
            ov += 1
    L += ["", f"Lệnh H1 trùng thời gian và cùng chiều với ít nhất một chân S07 M30: **{ov / max(len(rows), 1):.0%}** ({ov}/{len(rows)}).", ""]
    m30 = [dict(t_in=x["u_in"], t_out=x["u_out"], r=x["r"], risk=0.015 * x["w"]) for x in legs]
    h1 = [dict(t_in=t["utc"], t_out=int(t["utc"] + t["hold_h"] * 3600), r=t["r"], risk=0.015) for t in rows]
    per = [("09/2018–07/2021", ts("2018-09-01"), ts("2021-07-20")), ("07/2021–2023", ts("2021-07-20"), ts("2024-01-01")),
           ("2024–06/2025", ts("2024-01-01"), ts("2025-07-01")), ("07/2025–06/2026", ts("2025-07-01"), ts("2026-07-01"))]
    L += ["Danh mục (1,5% mỗi lệnh, lãi kép). Ô: %/năm / DD / **MAR** / lệnh:", "",
          "| Sổ | " + " | ".join(p for p, _, _ in per) + " |", "|---|---|---|---|---|"]
    for name, book in (("S07 M30 một mình", m30), ("S07 H1 một mình", h1), ("S07 M30 + H1", m30 + h1)):
        L.append(f"| {name} | " + " | ".join(fmt(sim(book, a, b)) for _, a, b in per) + " |")
    L.append("")


def terminal_m30(n=60000):
    import MetaTrader5 as mt5
    if not mt5.initialize(path=TERMINAL):
        raise RuntimeError(mt5.last_error())
    try:
        r = mt5.copy_rates_from_pos("XAUUSD-VIP", mt5.TIMEFRAME_M30, 1, n)
    finally:
        mt5.shutdown()
    return pd.DataFrame(r).rename(columns={"tick_volume": "tickvol"})[["time", "open", "high", "low", "close", "tickvol", "spread"]]


def prep_v(m):
    from g97_forming_bar import dmi, ema
    m = m.copy().reset_index(drop=True)
    m["ts"] = pd.to_datetime(m["time"], unit="s")
    c = m["close"].to_numpy()
    for n in (21, 55, 100, 200):
        m[f"e{n}"] = ema(c, n)
    m["pdi"], m["mdi"], m["adx"], m["atr"] = dmi(m["high"].to_numpy(), m["low"].to_numpy(), c)
    m["sp"] = m["spread"] * 0.01
    return m


def candidate_a(m):
    import g116_v_hedge as g116
    import g118_v_combos as g118
    from g117_v_filters import Sim2
    gr = g116.find_groups(m)
    F = g118.features(m, gr)
    mask = (F["fan_against"] & F["adx_lt25"] & F["slope_against"]).to_numpy()
    S = Sim2(m)
    out = []
    for (v, j), keep in zip(gr, mask):
        if keep:
            r, _ = S.hedge_r(v, j, "A2")
            out.append(dict(t=m["ts"].iat[j], vdir=int(np.sign(m["close"].iat[v] - m["e200"].iat[v])), r=r))
    return pd.DataFrame(out)


def part3(L):
    import g118_v_combos as g118
    hist = candidate_a(g118.load("M30"))
    ok = hist["r"].notna()
    by = hist[ok].groupby(hist[ok]["t"].dt.year)["r"].agg(["count", "mean"])
    L += ["## 3. Nến V M30 (G118 ứng viên A): tái lập và forward", "",
          f"**Tái lập trên dữ liệu nghiên cứu** (stop ± 2 ATR): {int(ok.sum())} nhóm, **{hist.loc[ok, 'r'].mean():+.3f}U/nhóm** "
          f"(G118 báo cáo 211 nhóm, +0,42U).", "",
          "| Năm | " + " | ".join(str(y) for y in by.index) + " |", "|---|" + "---|" * len(by),
          "| Nhóm / U | " + " | ".join(f"{int(r['count'])} / {r['mean']:+.2f}" for _, r in by.iterrows()) + " |", ""]
    try:
        fw = candidate_a(prep_v(terminal_m30()))
        fw = fw[fw["t"] >= pd.Timestamp("2026-10-10")]
        L += [f"**Forward từ 10/10/2026** (nến M30 terminal XAUUSD-VIP, chỉ đọc): {len(fw)} nhóm.", ""]
        if len(fw):
            L += ["| Nến quay về (server) | Chiều V | Kết quả (U) |", "|---|---|---|"]
            for r in fw.itertuples():
                L.append(f"| {r.t:%Y-%m-%d %H:%M} | {'lên' if r.vdir == 1 else 'xuống'} | {'đang mở' if r.r != r.r else f'{r.r:+.2f}'} |")
            L.append("")
    except Exception as ex:
        L += [f"Forward: không đọc được terminal ({ex}).", ""]


def part4(L):
    import g106_shadow as sh
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            sh.main()
        txt = (HERE.parent / "forward" / "g106_shadow_summary.md").read_text(encoding="utf-8")
        body = [ln for ln in txt.splitlines() if not ln.startswith("# ")]
        L += ["## 4. CtxBox (G106) — forward từ 12/10/2026", ""] + body + [""]
    except Exception as ex:
        L += ["## 4. CtxBox (G106) — forward", "", f"Không chạy được ({ex}).", ""]


def main():
    L = ["# G134: bốn hướng mở rộng — kết quả", "", "Kế hoạch: `plans/2026-10-21-g134-four-extensions.md`. "
         "Tính lại sổ, so sánh và forward; không có kỳ kín mới.", ""]
    legs = s07_legs()
    print("legs", len(legs), flush=True)
    part1(L, legs)
    print("part1", flush=True)
    part2(L, legs)
    print("part2", flush=True)
    part3(L)
    print("part3", flush=True)
    part4(L)
    print("part4", flush=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
