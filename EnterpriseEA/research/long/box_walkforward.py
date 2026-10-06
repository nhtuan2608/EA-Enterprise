"""G37: walk-forward choice of the S06B box length (18..30, USD flow, contraction 0.85). MT5 data only.

Each year 2014-2025 uses the box with the best mean R over all earlier years (at least 30 trades), so the
result never sees the year it trades. Compared with the fixed box 24 and with the average of all boxes.
"""
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool
import statistics

import long_study as ls  # noqa: F401  (research data path)
import filters  # noqa: E402
import replay  # noqa: E402
import robustness as rb  # noqa: E402
import setups  # noqa: E402

BOXES = list(range(18, 31))


def rows_job(box: int):
    out = []
    for s in ls.SYMBOLS:
        c = rb._C[s]
        bars = c["entry"]
        shift = bars[0]["time"] - bars[0]["utc"]
        t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
        for x in setups.s06(c, dict(filters.S06B, box=box)):
            r = replay.evaluate(c, x, "S06", "SWING", "tm", t)
            if r["status"] != "EVALUATED":
                continue
            flow = rb._USD.get(bars[x["i"]]["time"], 0)
            if flow == 0 or x["direction"] * filters.USD_SIGN[s] != flow:
                continue
            out.append((datetime.fromtimestamp(bars[x["i"]]["time"] - shift, timezone.utc).year, r["r"]))
    return box, out


if __name__ == "__main__":
    with Pool(12, initializer=rb.init_params_worker, initargs=(filters.usd_index(),)) as pool:
        res = dict(pool.map(rows_job, BOXES))
    by = {b: defaultdict(list) for b in BOXES}
    for b, rows in res.items():
        for y, r in rows:
            by[b][y].append(r)
    wf, fixed, avg, picks = [], [], [], []
    for year in range(2014, 2026):
        past = {b: [r for y, rs in by[b].items() if y < year for r in rs] for b in BOXES}
        ok = {b: statistics.fmean(v) for b, v in past.items() if len(v) >= 30}
        pick = max(ok, key=ok.get)
        picks.append((year, pick))
        wf += by[pick].get(year, [])
        fixed += by[24].get(year, [])
        avg += [r for b in BOXES for r in by[b].get(year, [])]
    f = lambda v: f"{statistics.fmean(v):+.3f} (n={len(v)}, tổng {sum(v):+.1f}R)"  # noqa: E731
    print("Hộp được chọn mỗi năm: " + ", ".join(f"{y}:{b}" for y, b in picks))
    print(f"Walk-forward 2014-2025: {f(wf)}")
    print(f"Hộp 24 cố định 2014-2025: {f(fixed)}")
    print(f"Trung bình mọi hộp 18-30 2014-2025: {f(avg)}")
