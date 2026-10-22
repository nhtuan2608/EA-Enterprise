"""G151: per-bot time map (hour bucket, weekday, month position, NFP / Fed day, 2 h before a HIGH USD event) for the S07 M30,
T2 XAU, CtxLimit and XauRegime research books. Plan: docs/superpowers/plans/2026-10-22-g151-bot-time-map.md.

Usage: g151_bot_time_map.py <data dir> <out.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402
import g147_risk_map as rm  # noqa: E402
import g148_layered_risk_map as lm  # noqa: E402
from g134_extensions import sim  # noqa: E402

H = 3600
PERMS = 5000


def ts(y, m=1, d=1):
    return g.ts(y, m, d)


BOTS = {
    "S07 M30": dict(sel=(2018, 2019, 2020, 2021), need=3,
                    per=[("chọn", ts(2018, 5), ts(2022)), ("2022–23", ts(2022), ts(2024)), ("2024–06/2026", ts(2024), ts(2026, 7))]),
    "T2 XAU": dict(sel=(2018, 2019, 2020, 2021), need=3,
                   per=[("chọn", ts(2018), ts(2022)), ("2022–23", ts(2022), ts(2024)), ("2024–10/2025", ts(2024), ts(2026))]),
    "CtxLimit": dict(sel=(2020, 2021), need=2,
                     per=[("chọn", ts(2020), ts(2022)), ("2022–23", ts(2022), ts(2024)), ("2024–2026", ts(2024), ts(2027))]),
    "XauRegime": dict(sel=tuple(range(2010, 2018)), need=6, daily=True,
                      per=[("chọn", ts(2010), ts(2018)), ("2018–21", ts(2018), ts(2022)), ("2022–06/2026", ts(2022), ts(2026, 7))]),
}


def books(root):
    out = {}
    g.set_tf("M30")
    g.DATA = root / "m30v"
    D = rm.prepare(g.load("XAUUSD"))
    import g136_p1p4 as p1
    b = []
    for x in p1.m30_book():
        k = int(np.searchsorted(D["t"], x["srv"], side="right")) - 1
        w = x["w"] * (1.0 if D["d1"][k] == x["d"] else 0.5)
        b.append(dict(srv=x["srv"], t_in=x["ein"], t_out=x["eout"], r=x["r"], risk=0.015 * w))
    out["S07 M30"] = b
    import discovery as dsc
    B = dsc.load("XAUUSD", "H4")
    out["T2 XAU"] = [dict(srv=int(B["t"][t["i"]]) + 14400, t_in=int(B["utc"][t["i"]]) + 14400,
                          t_out=int(B["utc"][t["exit_i"]]) + 14400, r=float(t["r"]), risk=0.005)
                     for t in dsc.trades("T2", {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}, "XAUUSD")]
    import g107_portfolio as p107
    sec = lambda x: int(pd.Timestamp(x).value // 10 ** 9)
    out["CtxLimit"] = [dict(srv=sec(x["t_in"]), t_in=sec(x["t_in"]), t_out=sec(x["t_out"]), r=float(x["r"]),
                            risk=float(x["money"]) / p107.CAPITAL) for x in p107.ctx_legs()]
    out["XauRegime"] = [dict(srv=sec(x["t_in"]), t_in=sec(x["t_in"]), t_out=sec(x["t_out"]) + 86399, r=float(x["r"]), risk=0.015)
                        for x in p107.xrt_legs()]
    return out


def month_positions():
    from g96_regime import load_d1
    days = sorted({int(pd.Timestamp(x).value // 10 ** 9 // 86400) for x in load_d1()["day"]})
    mon = np.array(days, dtype="datetime64[D]").astype("datetime64[M]").astype(int)
    pos = {}
    for m_ in np.unique(mon):
        idx = [days[k] for k in np.nonzero(mon == m_)[0]]
        for j, dk in enumerate(idx):
            pos[dk] = "2 ngày đầu" if j <= 1 else ("2 ngày cuối" if j >= len(idx) - 2 else "giữa")
    return pos


def states(x, daily, mpos, hi, nfp, fed):
    srv = x["srv"]
    dk, hr = srv // 86400, (srv % 86400) // H
    s = {"thứ": ("T2", "T3", "T4", "T5", "T6", "T7", "CN")[int((dk + 3) % 7)],
         "trong tháng": mpos.get(int(dk), "giữa"), "ngày NFP": "có" if dk in nfp else "không",
         "ngày Fed": "có" if dk in fed else "không"}
    if not daily:
        s["giờ"] = ("Á sớm" if 1 <= hr <= 5 else ("Á muộn" if 6 <= hr <= 9 else ("London" if 10 <= hr <= 14 else
                                                                               ("New York" if 15 <= hr <= 19 else "tối"))))
        k = np.searchsorted(hi, srv)
        s["trước tin 2 giờ"] = "có" if k < len(hi) and hi[k] - srv <= 2 * H else "không"
    return s


def year(srv):
    return int(np.datetime64(int(srv), "s").astype("datetime64[Y]").astype(int) + 1970)


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    hi, nfp, fed = lm.calendar()
    mpos = month_positions()
    bk = books(root)
    total_states = 0
    tables = {}
    for name, book in bk.items():
        cfg = BOTS[name]
        for x in book:
            x["s"] = states(x, cfg.get("daily", False), mpos, hi, nfp, fed)
            x["y"] = year(x["srv"])
            x["p"] = next((pn for pn, a, z in cfg["per"] if a <= x["srv"] < z), None)
        book = [x for x in book if x["p"]]
        bk[name] = book
        tables[name] = {f: sorted({x["s"][f] for x in book}) for f in book[0]["s"]}
        total_states += sum(len(v) for v in tables[name].values())
    pthr = 0.05 / total_states
    res = {"ngưỡng p (0,05 / số trạng thái)": round(pthr, 5), "số trạng thái": total_states}
    for name, book in bk.items():
        cfg = BOTS[name]
        r = np.array([x["r"] for x in book])
        yrs = np.array([x["y"] for x in book])
        per = np.array([x["p"] for x in book], dtype=object)
        out = {"lệnh": len(book), "theo kỳ": {pn: [int((per == pn).sum()), round(float(r[per == pn].mean()), 3)] for pn, _, _ in cfg["per"]}}
        for f, sts in tables[name].items():
            for st in sts:
                has = np.array([x["s"][f] == st for x in book])
                row = {"tỷ lệ": round(float(has.mean()), 3)}
                row["Δ theo năm"] = {str(y): (round(float(r[(yrs == y) & has].mean() - r[(yrs == y) & ~has].mean()), 3)
                                              if ((yrs == y) & has).any() and ((yrs == y) & ~has).any() else None)
                                     for y in sorted(set(yrs.tolist()))}
                for pn, _, _ in cfg["per"]:
                    m = per == pn
                    row[f"Δ {pn}"] = round(float(r[m & has].mean() - r[m & ~has].mean()), 3) if (m & has).any() and (m & ~has).any() else None
                sel_d = [row["Δ theo năm"].get(str(y)) for y in cfg["sel"]]
                cand = ((row["Δ chọn"] is not None and row["Δ chọn"] <= -0.15)
                        and sum(v is not None and v < 0 for v in sel_d) >= cfg["need"] and 0.05 <= row["tỷ lệ"] <= 0.40)
                if cand:
                    base = [dict(t_in=x["t_in"], t_out=x["t_out"], r=x["r"], risk=x["risk"]) for x in book]
                    var = [dict(t_in=x["t_in"], t_out=x["t_out"], r=x["r"], risk=x["risk"] * (0.5 if x["s"][f] == st else 1.0)) for x in book]
                    row["MAR mốc / ×0,5"] = {pn: [round(sim(base, a, z)[2], 2), round(sim(var, a, z)[2], 2)] for pn, a, z in cfg["per"]}
                    act = r[has].mean() - r[~has].mean()
                    rng = np.random.default_rng(151)
                    hits = sum((r[s_].mean() - r[~s_].mean()) <= act for s_ in (rng.permutation(has) for _ in range(PERMS)))
                    row["p hoán vị"] = round((hits + 1) / (PERMS + 1), 5)
                    later = [row[f"Δ {pn}"] for pn, _, _ in cfg["per"][1:]]
                    ok = (all(v is not None and v < 0 for v in later)
                          and all(v[1] >= v[0] for v in row["MAR mốc / ×0,5"].values()) and row["p hoán vị"] <= pthr)
                    row["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
                else:
                    row["kết luận"] = "không thành ứng viên"
                out[f"{f}: {st}"] = row
        res[name] = out
        print(name, [(k, v["kết luận"], v.get("Δ chọn"), v.get("p hoán vị")) for k, v in out.items()
                     if isinstance(v, dict) and v.get("kết luận") not in (None, "không thành ứng viên")], flush=True)
    Path(sys.argv[2]).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
