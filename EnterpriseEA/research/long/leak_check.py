"""Look-ahead (leakage) audit: signals computed on data cut at time T must equal the full-data signals before T.

  python leak_check.py

For each cut date the bar files (H1, H4, D1 of the five symbols) are truncated to the bars that had closed
before the cut, the research code runs again in a fresh process on those files only, and its signals are
compared with the signals of the full data that fall before the cut. Any signal that changes when the
future is removed means the code looked ahead. Checked: S04 SWING candidates (time, side, stop anchor),
S06B candidates and their USD-flow flag, T2 signals (time, side, stop in ATR). Trade results are not
compared: they need the bars after the entry by definition.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
CUTS = ["2015-06-01", "2019-03-01", "2023-09-01", "2025-06-01"]

WORKER = r'''
import json, sys
from pathlib import Path
import long_study as ls
import context
data = Path(sys.argv[1]); cache = Path(sys.argv[2])
context.DATA = data; context.CACHE = cache; ls._CTX.clear()
import discovery as dv, filters, replay, setups, exits
dv._BARS.clear()
usd = filters.usd_index()
out = {"S04": [], "S06B": [], "T2": []}
for s in ls.SYMBOLS:
    c = ls.ctx(s, "SWING")
    if c is None or dv.load(s, "H4") is None:
        continue
    bars = c["entry"]
    for x in replay.candidates(c, "S04", replay.engine_params("S04", "SWING")):
        out["S04"].append([s, bars[x["i"]]["time"], x["direction"], round(x["extreme"], 8)])
    for x in setups.s06(c, filters.S06B):
        t = bars[x["i"]]["time"]
        flow = usd.get(t, 0)
        ok = flow != 0 and x["direction"] * filters.USD_SIGN[s] == flow
        out["S06B"].append([s, t, x["direction"], round(x["extreme"], 8), ok])
    B = dv.load(s, "H4")
    p = {"n": 60, "stop": 2.0, "trail": 3.0, "d1": True, "timeout": 180}
    for i, d, st in dv.sig_t2(B, p):
        out["T2"].append([s, int(B["t"][i]), d, round(st, 6)])
print(json.dumps(out))
'''


def run(data: Path) -> dict:
    cache = Path(tempfile.mkdtemp(prefix="leak-cache-"))
    try:
        proc = subprocess.run([sys.executable, "-c", WORKER, str(data), str(cache)], cwd=str(HERE),
                              capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2000:])
        return json.loads(proc.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def truncate(cut_server: int) -> Path:
    d = Path(tempfile.mkdtemp(prefix="leak-data-"))
    shutil.copy(DATA / "bars_meta.json", d / "bars_meta.json")
    for s in SYMBOLS:
        for tf, sec in (("H1", 3600), ("H4", 14400), ("D1", 86400)):
            src = DATA / f"bars_{s}_{tf}.csv"
            if not src.exists():
                continue
            with src.open(encoding="utf-8") as fh, (d / src.name).open("w", encoding="utf-8", newline="") as out:
                out.write(fh.readline())
                kept = 0
                for line in fh:
                    if int(line.split(",", 1)[0]) + sec <= cut_server:      # only bars closed before the cut
                        out.write(line)
                        kept += 1
            if kept < 500:                     # symbol not traded yet at the cut (XAUUSD, BTCUSD before 2018)
                (d / src.name).unlink()
    return d


def main() -> None:
    full = run(DATA)
    lines = ["# Kiểm tra rò rỉ dữ liệu tương lai (look-ahead) bằng cắt cụt dữ liệu", "",
             "| Cắt tại | Setup | Tín hiệu trước mốc (đủ dữ liệu) | Khớp khi chỉ có dữ liệu trước mốc | Khác | Thiếu / thừa |",
             "|---|---|---|---|---|---|"]
    total_bad = 0
    for cut in CUTS:
        cut_server = int(datetime.fromisoformat(cut).replace(tzinfo=timezone.utc).timestamp())
        d = truncate(cut_server)
        try:
            part = run(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        for setup in ("S04", "S06B", "T2"):
            # the last bars before the cut are compared too; only signals of bars closed before the cut
            sec = 14400 if setup == "T2" else 3600
            want = {tuple(x) for x in full[setup] if x[1] + sec <= cut_server}
            got = {tuple(x) for x in part[setup]}
            same = want & got
            bad = len(want ^ got)
            total_bad += bad
            only_full = sorted(want - got)[:2]
            only_cut = sorted(got - want)[:2]
            lines.append(f"| {cut} | {setup} | {len(want)} | {len(same)} | {bad} | "
                         f"{only_full or '-'} / {only_cut or '-'} |")
    lines += ["", f"**Tổng số tín hiệu thay đổi khi bỏ dữ liệu tương lai: {total_bad}**"]
    text = "\n".join(lines) + "\n"
    (HERE / "results" / "leak_check.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
