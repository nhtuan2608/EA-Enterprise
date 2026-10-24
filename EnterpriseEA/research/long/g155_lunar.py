"""G155: lunar calendar cells (moon phase, new / full moon, 24 solar terms, lunar month) vs gold daily direction, gold daily
range and S07 leg R, with a family-wise null from shifted lunar labels. Plan: docs/superpowers/plans/2026-10-24-g155-lunar-calendar.md.

Usage: g155_lunar.py <data dir> <out.json>
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
from lunar_python import Solar

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g67_dmi_ema as g  # noqa: E402

SHIFTS, MIN_GAP, SEED = 2000, 30, 155
P_FAMILY = 0.05 / 3
GOLD_PER = [("2010–2015", dt.date(2010, 1, 1), dt.date(2016, 1, 1)), ("2016–2020", dt.date(2016, 1, 1), dt.date(2021, 1, 1)),
            ("2021–06/2026", dt.date(2021, 1, 1), dt.date(2026, 7, 1))]
S07_PER = [("05/2018–2021", dt.date(2018, 5, 1), dt.date(2022, 1, 1)), ("2022–2023", dt.date(2022, 1, 1), dt.date(2024, 1, 1)),
           ("2024–06/2026", dt.date(2024, 1, 1), dt.date(2026, 7, 1))]
AFTER = (dt.date(2026, 7, 1), dt.date(2100, 1, 1))


def gold_days(root):
    """Server-day OHLC from the M30 file (D1 bars before 2018-03-19)."""
    days = {}
    with open(root / "m30v" / "XAUUSD.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            t = int(r["time"])
            k = t // 86400
            o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
            if k not in days:
                days[k] = [o, h, l, c]
            else:
                x = days[k]
                x[1], x[2], x[3] = max(x[1], h), min(x[2], l), c
    keys = sorted(days)
    a = np.array([days[k] for k in keys])
    date = [dt.date(1970, 1, 1) + dt.timedelta(days=int(k)) for k in keys]
    rng = a[:, 1] - a[:, 2]
    atr = np.full(len(a), np.nan)
    for i in range(20, len(a)):
        atr[i] = rng[i - 20:i].mean()
    return date, (a[:, 3] - a[:, 0]) / atr, rng / atr


_TERMS = {}
# getJieQiTable also lists the next year's first terms under pinyin keys: fold them into the 24 Chinese names
PINYIN = {"DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒", "LI_CHUN": "立春", "YU_SHUI": "雨水", "JING_ZHE": "惊蛰"}


def term_starts(year):
    if year not in _TERMS:
        tbl = Solar.fromYmd(year, 6, 1).getLunar().getJieQiTable()
        _TERMS[year] = sorted((dt.date(s.getYear(), s.getMonth(), s.getDay()), PINYIN.get(name, name)) for name, s in tbl.items())
    return _TERMS[year]


def cells_of(d):
    """The cell labels (one per family) of a calendar date."""
    lu = Solar.fromYmd(d.year, d.month, d.day).getLunar()
    day, month = lu.getDay(), abs(lu.getMonth())
    phase = "ngày âm 1–7" if day <= 7 else "ngày âm 8–15" if day <= 15 else "ngày âm 16–22" if day <= 22 else "ngày âm 23–30"
    moon = "quanh sóc (29–2)" if day in (29, 30, 1, 2) else "quanh vọng (14–16)" if day in (14, 15, 16) else None
    starts = [x for y in (d.year - 1, d.year) for x in term_starts(y)]
    term = max((x for x in starts if x[0] <= d), key=lambda x: x[0])[1]
    return {"pha trăng": phase, "sóc/vọng": moon, "tiết khí": "tiết " + term, "tháng âm": f"tháng {month}"}


def label_matrix(dates):
    labs = [cells_of(d) for d in dates]
    names = sorted({v for L in labs for v in L.values() if v})
    M = np.zeros((len(names), len(dates)), bool)
    pos = {n: i for i, n in enumerate(names)}
    for j, L in enumerate(labs):
        for v in L.values():
            if v:
                M[pos[v], j] = True
    return names, M


def welch(y, m):
    a, b = y[m], y[~m]
    if len(a) < 10 or len(b) < 10:
        return 0.0
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else 0.0


def tstats(y, M):
    return np.array([welch(y, m) for m in M])


def family_null(y, M, rng):
    """Max |t| over all cells with the lunar labels shifted circularly by k trading days."""
    n = M.shape[1]
    out = np.empty(SHIFTS)
    for s in range(SHIFTS):
        k = int(rng.integers(MIN_GAP, n - MIN_GAP))
        out[s] = np.abs(tstats(y, np.roll(M, k, axis=1))).max()
    return out


def analyse(name, dates, y, periods, rng, filter_check=False):
    keep = np.isfinite(y) & np.array([periods[0][1] <= d < periods[-1][2] for d in dates])
    d_in = [d for d, k in zip(dates, keep) if k]
    yk = y[keep]
    names, M = label_matrix(d_in)
    t = tstats(yk, M)
    best = int(np.argmax(np.abs(t)))
    null = family_null(yk, M, rng)
    p = float(((null >= abs(t[best])).sum() + 1) / (SHIFTS + 1))
    per = []
    for pn, a, z in periods:
        sel = np.array([a <= d < z for d in d_in])
        m = M[best] & sel
        per.append({"kỳ": pn, "trong ô": round(float(yk[m].mean()), 3) if m.any() else None, "n": int(m.sum()),
                    "ngoài ô": round(float(yk[sel & ~M[best]].mean()), 3)})
    sign = np.sign(t[best])
    same = all(x["trong ô"] is not None and np.sign(x["trong ô"] - x["ngoài ô"]) == sign for x in per)
    cells = sorted(({"ô": names[i], "n": int(M[i].sum()), "TB trong ô": round(float(yk[M[i]].mean()), 3),
                     "TB ngoài ô": round(float(yk[~M[i]].mean()), 3), "t": round(float(t[i]), 2)} for i in range(len(names))),
                   key=lambda r: -abs(r["t"]))
    res = {"mục tiêu": name, "số ngày / lệnh": int(len(yk)), "TB chung": round(float(yk.mean()), 3),
           "ô mạnh nhất": names[best], "t": round(float(t[best]), 2), "p cả họ (2.000 lần dịch)": round(p, 4),
           "|t| null p50 / p95 / p99": [round(float(np.percentile(null, q)), 2) for q in (50, 95, 99)],
           "ô mạnh nhất theo kỳ": per, "cùng dấu cả 3 kỳ": bool(same), "các ô (xếp theo |t|)": cells}
    ok = p <= P_FAMILY and same
    if filter_check:
        # skip the cell when it is worse than the rest, keep only it when better
        f = []
        for pn, a, z in periods:
            sel = np.array([a <= d < z for d in d_in])
            base = yk[sel].mean()
            filt = yk[sel & (~M[best] if sign < 0 else M[best])].mean()
            f.append({"kỳ": pn, "không lọc": round(float(base), 3), "có lọc": round(float(filt), 3)})
        res["dùng làm bộ lọc S07"] = f
        ok = ok and all(x["có lọc"] > x["không lọc"] for x in f)
    res["kết luận"] = "ĐẠT" if ok else "KHÔNG ĐẠT"
    print(name, res["ô mạnh nhất"], res["t"], res["p cả họ (2.000 lần dịch)"], res["cùng dấu cả 3 kỳ"], res["kết luận"], flush=True)
    return res


def main():
    root = Path(sys.argv[1]).resolve()
    g.HERE = root.parent
    rng = np.random.default_rng(SEED)
    dates, ret, rng_atr = gold_days(root)
    out = {"T1 hướng giá ngày (đóng−mở)/ATR20": analyse("T1", dates, ret, GOLD_PER, rng),
           "T2 biến động ngày (cao−thấp)/ATR20": analyse("T2", dates, rng_atr, GOLD_PER, rng)}
    import g136_p1p4 as p1
    g.set_tf("M30")
    g.DATA = root / "m30v"
    legs = p1.m30_book()
    ld = [dt.date(1970, 1, 1) + dt.timedelta(days=x["srv"] // 86400) for x in legs]
    order = np.argsort([x["srv"] for x in legs], kind="stable")
    ld = [ld[i] for i in order]
    lr = np.array([legs[i]["r"] for i in order])
    out["T3 R chân S07"] = analyse("T3", ld, lr, S07_PER, rng, filter_check=True)
    # after-period report
    aft = {}
    for key_, dd, yy in (("T1", dates, ret), ("T2", dates, rng_atr), ("T3", ld, lr)):
        res = out[[k for k in out if k.startswith(key_)][0]]
        sel = [i for i, d in enumerate(dd) if AFTER[0] <= d < AFTER[1] and np.isfinite(yy[i])]
        if sel:
            inc = [i for i in sel if res["ô mạnh nhất"] in cells_of(dd[i]).values()]
            aft[key_] = {"ô": res["ô mạnh nhất"], "n trong ô": len(inc),
                         "TB trong ô": round(float(np.mean(yy[inc])), 3) if inc else None,
                         "TB ngoài ô": round(float(np.mean([yy[i] for i in sel if i not in inc])), 3)}
    out["kỳ sau 07–10/2026 (báo cáo)"] = aft
    out["kết luận"] = "ĐẠT" if any(v.get("kết luận") == "ĐẠT" for v in out.values() if isinstance(v, dict)) else "KHÔNG ĐẠT"
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
