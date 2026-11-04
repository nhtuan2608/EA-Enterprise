"""Merge the user-supplied ingest data (D:\\Work\\Project Research\\Ingest-data\\ingest-20261104, UTC, no spread) with MT5 data, after an
overlap check against MT5 bars. Writes a validation report and merged daily series for G165 (XAU / XAG D1).

Usage: ingest_merge.py <ingest dir> <MT5 raw XAU D1 csv> <dir with mt5_XAUUSD_D1.csv / mt5_XAGUSD_D1.csv> <out dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def ingest(root, sym, tf):
    d = pd.read_csv(Path(root) / sym / f"{sym}_{tf}.csv.gz")
    d["time_utc"] = pd.to_datetime(d["time_utc"])
    return d


def mt5_d1(path):
    d = pd.read_csv(path)
    d["date"] = pd.to_datetime(d["time"], unit="s").dt.normalize()
    return d.rename(columns={"spread": "spread_pts"})[["date", "open", "high", "low", "close", "spread_pts"]]


def raw_d1(path):
    d = pd.read_csv(path, sep="\t")
    d = pd.DataFrame({"date": pd.to_datetime(d["<DATE>"], format="%Y.%m.%d"), "open": d["<OPEN>"], "high": d["<HIGH>"], "low": d["<LOW>"],
                      "close": d["<CLOSE>"], "spread_pts": d["<SPREAD>"]})
    return d


def check(name, ing, ref, shifts=(-1, 0, 1)):
    """Match ingest daily bars to MT5 server dates: try date shifts, report the best by close agreement."""
    out = {}
    best = None
    for s in shifts:
        x = ing.copy()
        x["date"] = x["time_utc"].dt.normalize() + pd.Timedelta(days=s)
        m = x.merge(ref, on="date", suffixes=("_i", "_m"))
        if len(m) < 50:
            continue
        rel = (m["close_i"] / m["close_m"] - 1).abs()
        ri, rm = np.log(m["close_i"]).diff(), np.log(m["close_m"]).diff()
        r = {"ngày trùng": int(len(m)), "chênh close TB %": round(float(rel.mean() * 100), 3), "chênh close p95 %": round(float(rel.quantile(0.95) * 100), 3),
             "tương quan lợi suất ngày": round(float(ri.corr(rm)), 4)}
        out[f"dịch {s:+d} ngày"] = r
        if best is None or r["chênh close TB %"] < out[best]["chênh close TB %"]:
            best = f"dịch {s:+d} ngày"
    return {"mã": name, "kết quả": out, "khớp nhất": best}


def main():
    ing_root, raw_xau, mt5_dir, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    xau_raw = raw_d1(raw_xau)
    xau_m = mt5_d1(mt5_dir / "mt5_XAUUSD_D1.csv")
    xag_m = mt5_d1(mt5_dir / "mt5_XAGUSD_D1.csv")
    xau_i, xag_i = ingest(ing_root, "XAUUSD", "1d"), ingest(ing_root, "XAGUSD", "1d")
    rep = {"XAU ingest vs MT5 raw D1 (2010–2025)": check("XAUUSD", xau_i, xau_raw),
           "XAU ingest vs MT5 terminal D1 (2024–2026)": check("XAUUSD", xau_i, xau_m),
           "XAG ingest vs MT5 terminal D1 (2024–2026)": check("XAGUSD", xag_i, xag_m)}
    xau_hr = sorted(set(xau_i["time_utc"].dt.hour)), sorted(set(xag_i["time_utc"].dt.hour))
    rep["giờ UTC của nến ingest (XAU, XAG)"] = [list(map(int, xau_hr[0]))[:6], list(map(int, xau_hr[1]))[:6]]
    # merged XAU: MT5 raw to its end, then MT5 terminal; merged XAG: ingest (best shift) to its end, then MT5 terminal
    xau = pd.concat([xau_raw, xau_m[xau_m["date"] > xau_raw["date"].max()]], ignore_index=True)
    s = int(rep["XAG ingest vs MT5 terminal D1 (2024–2026)"]["khớp nhất"].split()[1])
    xi = xag_i.copy()
    xi["date"] = xi["time_utc"].dt.normalize() + pd.Timedelta(days=s)
    xi["spread_pts"] = np.nan
    xi = xi[["date", "open", "high", "low", "close", "spread_pts"]]
    xag = pd.concat([xi, xag_m[xag_m["date"] > xi["date"].max()]], ignore_index=True)
    xag["spread_pts"] = xag["spread_pts"].fillna(float(xag_m["spread_pts"].median()))
    xau["spread_pts"] = xau["spread_pts"].where(xau["spread_pts"] > 0, float(xau_m["spread_pts"].median()))
    xau.to_csv(out / "merged_XAUUSD_D1.csv", index=False)
    xag.to_csv(out / "merged_XAGUSD_D1.csv", index=False)
    rep["chuỗi gộp"] = {"XAU": [str(xau["date"].min().date()), str(xau["date"].max().date()), len(xau)],
                        "XAG": [str(xag["date"].min().date()), str(xag["date"].max().date()), len(xag)],
                        "XAG: nối ingest → MT5 tại": str(xi["date"].max().date()), "dịch ngày XAG ingest": s}
    (out / "ingest_validation.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
