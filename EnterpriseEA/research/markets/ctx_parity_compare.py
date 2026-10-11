"""Compare the EA's decision log (Common\Files\CtxLimitTester_parity.csv, InpParityFile=true) with the Python
features and forecasts (ctx_parity.csv) on the same M30 decision bars.

  python ctx_parity_compare.py [path to CtxLimitTester_parity.csv]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
COMMON = Path(os.environ.get("APPDATA", "")) / "MetaQuotes" / "Terminal" / "Common" / "Files" / "CtxLimitTester_parity.csv"


def main():
    ea = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else COMMON)
    py = pd.read_csv(HERE / "ctx_parity.csv")
    m = ea.merge(py, on="time", suffixes=("_ea", "_py"))
    print(f"EA decisions {len(ea)}, Python decisions {len(py)}, matched bars {len(m)}")
    cols = [c[:-3] for c in m.columns if c.endswith("_ea")]
    for c in cols:
        a, b = m[c + "_ea"].astype(float), m[c + "_py"].astype(float)
        both = a.notna() & b.notna()
        d = (a[both] - b[both]).abs()
        print(f"{c:10s} nan EA/Py {int(a.isna().sum()):5d}/{int(b.isna().sum()):5d}  median |diff| {d.median():.2e}  p95 {d.quantile(.95):.2e}")


if __name__ == "__main__":
    main()
