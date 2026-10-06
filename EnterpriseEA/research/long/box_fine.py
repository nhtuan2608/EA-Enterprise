"""G37: S06B (USD flow) box length 18..30 one bar at a time: how sharp is the peak at 24? MT5 data only."""
from multiprocessing import Pool

import long_study as ls  # noqa: F401  (research data path)
import filters  # noqa: E402
import robustness as rb  # noqa: E402

if __name__ == "__main__":
    jobs = [("S06B", {"box": b, "contraction": c}) for b in range(18, 31) for c in (0.85, 1.0)]
    with Pool(12, initializer=rb.init_params_worker, initargs=(filters.usd_index(),)) as pool:
        res = pool.map(rb.params_job, jobs)
    print("| Hộp | Co hẹp | Train | Validate | Test |\n|---|---|---|---|---|")
    for r in res:
        print(f"| {r['p']['box']} | {r['p']['contraction']} | " + " | ".join(
            f"{r[k]['exp']:+.3f} (n={r[k]['n']})" for k in ("train", "validate", "test")) + " |")
