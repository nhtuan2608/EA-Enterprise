"""G37: multi-dimensional robustness audit of S04 and S06B, and the choice of the method. MT5 data only.

  python robustness.py            # every part
  python robustness.py random     # one part: random | params | portfolio

Signals: S04 SWING and S06B (USD flow, +1R add) on the five original symbols, SWING H1 2010-2025,
current Trade Manager, stops that a bar opens beyond fill at the open (pyramid.GAP_FILL).

1. RANDOM   each real trade is moved to a random bar of the same symbol and year with a random
            side, keeping its stop size (in ATR), its target (in R) and the Trade Manager; 2,000
            runs. p = share of random runs whose mean R reaches the real one. A second test keeps
            the real side (timing only).
2. PARAMS   neighbours of the chosen parameters (S06B: box, contraction, box height; S04: break
            buffer, return and trigger windows, invalidation buffer): share of neighbours positive
            in all three periods. An edge that lives on one exact parameter set is a fit.
3. PORTFOLIO the FTMO 1-Step account at 0.3% per trade: leave one symbol out, leave one setup out,
            without the best 5 / 10 trades, costs x2 and 0.1R extra slippage per trade, and a block
            bootstrap of months (2,000 resamples) for the 10th percentile of the yearly return and the
            90th percentile of the drawdown.
4. CHOICE   candidate methods ranked by the bootstrap 10th percentile of the yearly return divided by
            the 90th percentile of the drawdown, among those whose setups beat random entries
            (p < 0.10). The winner is the method to run.
"""
from __future__ import annotations

import itertools
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np

import long_study as ls  # sets the research data path and sys.path first
import exits  # noqa: E402
import filters  # noqa: E402
import fixed_lot as fl  # noqa: E402
import pyramid  # noqa: E402
import replay  # noqa: E402
import setups  # noqa: E402

RANDOM_RUNS = 2000
BOOT = 2000
_C: dict = {}
_POOLS: dict = {}


def init_worker() -> None:
    pyramid.GAP_FILL = True
    for s in ls.SYMBOLS:
        c = ls.ctx(s, "SWING")
        _C[s] = c
        bars = c["entry"]
        by_year = defaultdict(list)
        for j in range(60, len(bars) - 2):
            if bars[j]["atr"] > 0 and bars[j]["time"] >= c["from_server"]:
                by_year[datetime.fromtimestamp(bars[j]["utc"], timezone.utc).year].append(j)
        _POOLS[s] = {y: np.array(v) for y, v in by_year.items()}


def signals() -> dict:
    usd, dxy = filters.usd_index(), filters.real_dxy()
    return {name: [t for s in ls.SYMBOLS for t in exits.trades(name, s, usd, dxy)] for name in ("S04", "S06B", "S06B_USD")}


def real_r(sig: list[dict], add_at) -> list[float]:
    return [pyramid.run(_C[t["symbol"]], t, pyramid.CURRENT, add_at)["r"] for t in sig]


def random_chunk(job) -> list[tuple[float, float]]:
    """(mean R with random side, mean R with the real side) for `runs` random relocations."""
    sig, add_at, runs, seed = job
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(runs):
        tot_rand = tot_same = 0.0
        for t in sig:
            c = _C[t["symbol"]]
            bars, point = c["entry"], c["point"]
            i = t["i"]
            risk = abs(t["entry"] - t["stop"])
            risk_atr = risk / bars[i]["atr"]
            target_r = abs(t["target"] - t["entry"]) / risk
            year = datetime.fromtimestamp(t["utc"], timezone.utc).year
            pool = _POOLS[t["symbol"]].get(year)
            for keep_side in (False, True):
                j = int(pool[rng.integers(len(pool))])
                d = t["dir"] if keep_side else (1 if rng.random() < 0.5 else -1)
                b = bars[j]
                entry = b["close"] + (b["spread"] * point if d == 1 else 0.0)
                rk = risk_atr * b["atr"]
                tt = {"symbol": t["symbol"], "i": j, "dir": d, "entry": entry, "stop": entry - d * rk,
                      "target": entry + d * target_r * rk, "zl": 0.0, "zh": 0.0}
                r = pyramid.run(c, tt, pyramid.CURRENT, add_at)["r"]
                if keep_side:
                    tot_same += r
                else:
                    tot_rand += r
        out.append((tot_rand / len(sig), tot_same / len(sig)))
    return out


def part_random(sig: dict, pool: Pool) -> dict:
    out = {}
    for name, add in (("S04", None), ("S06B", None), ("S06B_USD", None), ("S06B_USD", 1.0)):
        real = statistics.fmean(real_r(sig[name], add))
        chunks = pool.map(random_chunk, [(sig[name], add, RANDOM_RUNS // 12, 100 + k) for k in range(12)])
        sims = np.array([x for ch in chunks for x in ch])
        key = name + ("+add" if add else "")
        out[key] = {"real": real, "n": len(sig[name]),
                    "rand_mean": float(sims[:, 0].mean()), "rand_p95": float(np.quantile(sims[:, 0], 0.95)),
                    "p_random_side": float((sims[:, 0] >= real).mean()),
                    "same_mean": float(sims[:, 1].mean()), "same_p95": float(np.quantile(sims[:, 1], 0.95)),
                    "p_same_side": float((sims[:, 1] >= real).mean())}
    return out


# ---------------------------------------------------------------------------
# 2. Parameter neighbours
# ---------------------------------------------------------------------------
S06B_GRID = {"box": [16, 20, 24, 28, 32], "contraction": [0.75, 0.85, 0.95], "max_box_atr": [2.5, 3.0, 3.5]}
S04_GRID = {"break_buffer_atr": [0.05, 0.10, 0.15], "return_window": [2, 3, 4], "trigger_window": [2, 3, 4],
            "invalidation_buffer_atr": [0.05, 0.10, 0.15]}


def params_job(job) -> dict:
    name, p = job
    usd = _USD
    rows = []
    for s in ls.SYMBOLS:
        c = _C[s]
        bars = c["entry"]
        shift = bars[0]["time"] - bars[0]["utc"]
        if name == "S06B":
            t = {"target": "fixed", "fixed_r": 3.0, "min_rr": 3.0, "htf": "any", "costs": True}
            for x in setups.s06(c, dict(filters.S06B, **p)):
                r = replay.evaluate(c, x, "S06", "SWING", "tm", t)
                if r["status"] != "EVALUATED":
                    continue
                flow = usd.get(bars[x["i"]]["time"], 0)
                if flow == 0 or x["direction"] * filters.USD_SIGN[s] != flow:
                    continue
                rows.append({"utc": bars[x["i"]]["time"] - shift, "r": r["r"]})
        else:
            for x in replay.candidates(c, "S04", replay.engine_params("S04", "SWING", p)):
                r = replay.evaluate(c, x, "S04", "SWING", "tm", {"costs": True})
                if r["status"] == "EVALUATED":
                    rows.append({"utc": bars[x["i"]]["time"] - shift, "r": r["r"]})
    v = exits.split(rows)
    return {"setup": name, "p": p, **{k: {"n": v[k]["n"], "exp": v[k]["exp"]} for k in ("train", "validate", "test")}}


_USD: dict = {}


def init_params_worker(usd: dict) -> None:
    init_worker()
    _USD.update(usd)


def part_params() -> dict:
    jobs = [("S06B", dict(zip(S06B_GRID, v))) for v in itertools.product(*S06B_GRID.values())]
    jobs += [("S04", dict(zip(S04_GRID, v))) for v in itertools.product(*S04_GRID.values())]
    with Pool(12, initializer=init_params_worker, initargs=(filters.usd_index(),)) as pool:
        res = pool.map(params_job, jobs)
    out = {}
    for name, center in (("S06B", {"box": 24, "contraction": 0.85, "max_box_atr": 3.0}),
                         ("S04", {"break_buffer_atr": 0.10, "return_window": 3, "trigger_window": 3,
                                  "invalidation_buffer_atr": 0.10})):
        rows = [r for r in res if r["setup"] == name]
        pos3 = [r for r in rows if min(r[k]["exp"] for k in ("train", "validate", "test")) > 0]
        c = next(r for r in rows if all(r["p"][k] == v for k, v in center.items()))
        out[name] = {"neighbours": len(rows), "positive_all3": len(pos3), "center": c,
                     "median": {k: statistics.median(r[k]["exp"] for r in rows) for k in ("train", "validate", "test")},
                     "rows": rows}
    return out


# ---------------------------------------------------------------------------
# 3 + 4. Portfolio checks and the choice
# ---------------------------------------------------------------------------
def account_rows(sig: list[dict], add_at, label: str) -> list[dict]:
    return exits.account_rows(_C, sig, pyramid.CURRENT, add_at, label)


def months_of(s: dict) -> np.ndarray:
    """Monthly result (% of the initial balance) on every calendar month 2010-01 .. 2025-10."""
    by = s["by_month_pct"]
    keys = [f"{y}-{m:02d}" for y in range(2010, 2026) for m in range(1, 13) if (y, m) <= (2025, 10)]
    return np.array([by.get(k, 0.0) for k in keys])


def bootstrap(months: np.ndarray, rng) -> dict:
    n = len(months)
    blocks = 6
    years = n / 12
    ann, dds = [], []
    for _ in range(BOOT):
        idx = np.concatenate([np.arange(st, st + blocks) % n for st in rng.integers(0, n, n // blocks + 1)])[:n]
        path = months[idx]
        eq = np.cumsum(path)
        dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq])) - np.concatenate([[0.0], eq])))
        ann.append(eq[-1] / years)
        dds.append(dd)
    return {"ann_p10": float(np.quantile(ann, 0.10)), "ann_p50": float(np.quantile(ann, 0.5)),
            "dd_p90": float(np.quantile(dds, 0.90)), "loss_prob": float(np.mean(np.array(ann) <= 0))}


def summary(rows: list[dict], rng) -> dict:
    s = fl.simulate(rows, "risk", {})
    y = s["by_year_pct"]
    b = bootstrap(months_of(s), rng)
    return {"per_year": s["per_year_pct"], "dd": s["max_dd_pct"], "pos_years": sum(1 for v in y.values() if v > 0),
            "years": len(y), "worst_year": min(y.values()), **b, "score": b["ann_p10"] / max(b["dd_p90"], 0.1)}


def part_portfolio(sig: dict) -> dict:
    rng = np.random.default_rng(11)
    s04 = account_rows(sig["S04"], None, "S04")
    s06u = account_rows(sig["S06B_USD"], None, "S06B")
    s06u_add = account_rows(sig["S06B_USD"], 1.0, "S06B")
    s06_add = account_rows(sig["S06B"], 1.0, "S06B")
    methods = {
        "M1 chỉ S04": s04,
        "M2 chỉ S06B lọc USD": s06u,
        "M3 chỉ S06B lọc USD + bồi": s06u_add,
        "M4 S04 + S06B lọc USD": s04 + s06u,
        "M5 S04 + S06B lọc USD + bồi": s04 + s06u_add,
        "M6 S04 + S06B (không lọc) + bồi": s04 + s06_add,
    }
    out = {"methods": {k: summary(v, rng) for k, v in methods.items()}}
    base = s04 + s06u_add
    checks = {}
    for sym in ls.SYMBOLS:
        checks[f"bỏ {sym}"] = summary([t for t in base if t["symbol"] != sym], rng)
    ranked = sorted(base, key=lambda t: t["r"], reverse=True)
    for k in (5, 10):
        top = {id(t) for t in ranked[:k]}
        checks[f"bỏ {k} lệnh lời nhất"] = summary([t for t in base if id(t) not in top], rng)
    fee = []
    for t in base:
        c = _C[t["symbol"]]
        extra = replay.COMMISSION.get(t["symbol"], 0.0) / max(t["dist"], 1e-12)
        fee.append(dict(t, r=t["r"] - extra))
    checks["phí ×2"] = summary(fee, rng)
    checks["trượt giá 0,1R mỗi lệnh"] = summary([dict(t, r=t["r"] - 0.1) for t in base], rng)
    checks["phí ×2 + trượt 0,1R"] = summary([dict(t, r=t["r"] - 0.1) for t in fee], rng)
    out["checks"] = checks
    return out


def fmt_p(x: float) -> str:
    return f"{x:.3f}" if x >= 0.001 else "<0.001"


def main(argv: list[str]) -> None:
    parts = argv or ["random", "params", "portfolio"]
    init_worker()
    sig = signals()
    res = {}
    lines = ["# G37: kiểm chứng độ bền nhiều chiều và chọn phương pháp (chỉ dữ liệu MT5)", ""]
    if "random" in parts:
        with Pool(12, initializer=init_worker) as pool:
            res["random"] = part_random(sig, pool)
        lines += ["## 1. So với vào lệnh ngẫu nhiên (2.000 lần, cùng dừng lỗ theo ATR, cùng R mục tiêu, cùng quản lý lệnh)", "",
                  "| Setup | Lệnh | R thật | Ngẫu nhiên cả chiều: TB / p95 / p | Ngẫu nhiên thời điểm, giữ chiều: TB / p95 / p |",
                  "|---|---|---|---|---|"]
        for k, v in res["random"].items():
            lines.append(f"| {k} | {v['n']} | {v['real']:+.3f} | {v['rand_mean']:+.3f} / {v['rand_p95']:+.3f} / {fmt_p(v['p_random_side'])} | "
                         f"{v['same_mean']:+.3f} / {v['same_p95']:+.3f} / {fmt_p(v['p_same_side'])} |")
        lines.append("")
    if "params" in parts:
        res["params"] = part_params()
        lines += ["## 2. Độ nhạy tham số (láng giềng của bộ tham số đang dùng)", "",
                  "| Setup | Số bộ láng giềng | Dương cả 3 giai đoạn | Trung vị train / validate / test | Bộ đang dùng train / validate / test |",
                  "|---|---|---|---|---|"]
        for name, v in res["params"].items():
            m, c = v["median"], v["center"]
            lines.append(f"| {name} | {v['neighbours']} | {v['positive_all3']} ({v['positive_all3'] / v['neighbours']:.0%}) | "
                         f"{m['train']:+.3f} / {m['validate']:+.3f} / {m['test']:+.3f} | "
                         f"{c['train']['exp']:+.3f} / {c['validate']['exp']:+.3f} / {c['test']['exp']:+.3f} |")
        s06 = res["params"]["S06B"]["rows"]
        lines += ["", "S06B lọc USD theo độ dài hộp (trung vị các bộ còn lại, train / validate / test):", ""]
        for box in S06B_GRID["box"]:
            rr = [r for r in s06 if r["p"]["box"] == box]
            lines.append(f"- hộp {box}: " + " / ".join(f"{statistics.median(r[k]['exp'] for r in rr):+.3f}"
                                                     for k in ("train", "validate", "test")))
        lines.append("")
    if "portfolio" in parts:
        res["portfolio"] = part_portfolio(sig)
        head = ("| Phương án | %/năm | DD | Năm dương | Năm tệ nhất | Bootstrap: %/năm p10 / p50 | DD p90 | Xác suất lỗ cả kỳ | Điểm (p10/DD p90) |",
                "|---|---|---|---|---|---|---|---|---|")

        def row(k, v):
            return (f"| {k} | {v['per_year']:+.2f}% | {v['dd']:.1f}% | {v['pos_years']}/{v['years']} | {v['worst_year']:+.1f}% | "
                    f"{v['ann_p10']:+.2f}% / {v['ann_p50']:+.2f}% | {v['dd_p90']:.1f}% | {v['loss_prob']:.0%} | {v['score']:.2f} |")
        lines += ["## 3. Danh mục (FTMO 1-Step, 0,3%/lệnh), kiểm tra căng thẳng trên M5 (S04 + S06B lọc USD + bồi)", "", *head]
        for k, v in res["portfolio"]["checks"].items():
            lines.append(row(k, v))
        lines += ["", "## 4. Chọn phương pháp", "", *head]
        meth = res["portfolio"]["methods"]
        for k, v in sorted(meth.items(), key=lambda kv: -kv[1]["score"]):
            lines.append(row(k, v))
        if "random" in res:
            ok = {k: v["p_random_side"] < 0.10 for k, v in res["random"].items()}
            need = {"M1 chỉ S04": ["S04"], "M2 chỉ S06B lọc USD": ["S06B_USD"], "M3 chỉ S06B lọc USD + bồi": ["S06B_USD+add"],
                    "M4 S04 + S06B lọc USD": ["S04", "S06B_USD"], "M5 S04 + S06B lọc USD + bồi": ["S04", "S06B_USD+add"],
                    "M6 S04 + S06B (không lọc) + bồi": ["S04", "S06B"]}
            eligible = [k for k in meth if all(ok.get(x, False) for x in need[k])]
            best = max(eligible, key=lambda k: meth[k]["score"]) if eligible else None
            lines += ["", "Đủ điều kiện (mọi setup trong phương án thắng vào lệnh ngẫu nhiên, p < 0,10): " + (", ".join(eligible) or "không có"),
                      f"**Phương án chọn: {best or 'không phương án nào đủ điều kiện'}**"]
            res["choice"] = best
    text = "\n".join(lines) + "\n"
    ls.OUT.mkdir(exist_ok=True)
    tag = "_".join(parts)
    (ls.OUT / f"robustness_{tag}.md").write_text(text, encoding="utf-8")
    (ls.OUT / f"robustness_{tag}.json").write_text(json.dumps(res, default=str), encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv[1:])
