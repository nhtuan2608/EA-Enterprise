"""G68 step 3: the 81 neighbours of the final rule (C0 + R1 + R3 + R5), appended to the G68 report."""
import itertools
import json
import sys
from multiprocessing import Pool

import numpy as np

import g68_refine as r

FINAL = {k: v for k, v in json.loads(r.REPORT.with_suffix(".final.json").read_text(encoding="utf-8")).items() if k != "guards"}


def job(v):
    p = dict(FINAL, adx_low=v[0], di_gap=v[1], rise=v[2], comp=v[3])
    return v, r.per(r.rows(p))


if __name__ == "__main__":
    grid = list(itertools.product((18.0, 20.0, 22.0), (4.0, 6.0, 8.0), (8.0, 10.0, 12.0), (6, 8, 10)))
    with Pool(12) as pool:
        nb = pool.map(job, grid)
    four = ("pre", "train", "validate", "test")
    all_ok = sum(1 for _, ps in nb if all(ps[k]["exp"] > 0 for k in four))
    exps = [np.mean([ps[k]["exp"] for k in four]) for _, ps in nb]
    lines = ["", "### Lân cận của bản cuối (81 bộ)", "",
             f"- Dương cả 4 kỳ (2018–2021, train, validate, test): {all_ok}/81 ({all_ok / 81:.0%})",
             f"- R/lệnh trung bình 4 kỳ: thấp nhất {min(exps):+.3f}, trung vị {np.median(exps):+.3f}, cao nhất {max(exps):+.3f}"]
    with open(r.REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
