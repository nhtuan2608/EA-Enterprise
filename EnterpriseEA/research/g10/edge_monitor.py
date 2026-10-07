"""G37 edge monitor: is the live edge still what the research measured? Read-only.

  python edge_monitor.py            # text for Telegram; writes <data root>/current/edge_monitor.json

Streams, each compared with its own research results (edge_params.json, research/long/edge_calibrate.py):
  S04_SWING thật                real S04 trades (logs/trades.jsonl, realized R)
  S06B_SWING thật               real S06B SWING first entries (trades.jsonl, realized R) since S06B_START_UTC
  S06B_SWING thật + bồi         the same per signal with its "-ADD1" leg added (R of both legs summed)
  S04_SWING ảo                  every S04 SWING candidate, as if it had run alone (candidates_eval)
  S06B_SWING ảo lọc USD         S06B candidates with the USD flow aligned (shadow)
  S06B_SWING ảo lọc USD + bồi   the same with the +1R add (shadow, G29)
  T2_POSITION ảo                every T2 candidate taken one per symbol at a time (shadow, G38)
  T2_POSITION ảo XAU+BTC        the same on the trend assets T2 may trade live (InpT2LiveSymbols, G41)
  T2_POSITION ảo XAU+BTC + bồi  the same with the +1R add (G44, r_add)
T2 streams count only candidates from T2_START_UTC (G44 deploy: momentum-close filter in the EA), so filtered
and unfiltered signals are never mixed; their parameters are calibrated on the filtered research (G46).
Checks, in trade order since START_UTC:
  CUSUM     downward CUSUM S_n = max(0, S_{n-1} + k - r_n), k = research mean / 2; WARN above h_warn,
            ALARM above h_alarm (false alarm about once per 250 trades when the edge is intact)
  DRAWDOWN  the largest drawdown in R against the 95th (WARN) / 99th (ALARM) percentile of the research
            drawdown after the same number of trades
  MEAN      from 20 trades on: ALARM when the 90% upper bound of the mean R is below zero
The monitor only reports; switching a setup back to SHADOW stays the operator's decision.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import candidates_eval as ce
import context

HERE = Path(__file__).resolve().parent
PARAMS = HERE / "edge_params.json"
START_UTC = int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp())   # G29 fields and the 2-Step session
LEVEL = {"NO_DATA": 0, "OK": 0, "WARN": 1, "ALARM": 2}
MIN_MEAN_TEST = 20
TREND_ASSETS = ("XAUUSD", "BTCUSD")   # G41: InpT2LiveSymbols default
S06B_START_UTC = int(datetime(2026, 10, 7, 16, 35, tzinfo=timezone.utc).timestamp())   # S06B switched to LIVE
ADD_SUFFIX = "-ADD1"   # EEA_S06B_ADD_SUFFIX: the +1R add is its own position, candidate_id = first id + suffix
T2_START_UTC = int(datetime(2026, 10, 6, 16, 36, tzinfo=timezone.utc).timestamp())   # G44 deployed (momentum filter)


def load_params(path: Path = PARAMS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["streams"]


def dd_limit(table: dict, n: int, key: str) -> float:
    """Research drawdown percentile for n trades (the next tabulated n at or above)."""
    ns = sorted(int(x) for x in table)
    pick = next((x for x in ns if x >= n), ns[-1])
    return float(table[str(pick)][key] if str(pick) in table else table[pick][key])


def check(rs: list[float], p: dict) -> dict:
    """Status of one stream of results (R, in time order) against its research parameters."""
    n = len(rs)
    if n == 0:
        return {"n": 0, "status": "NO_DATA", "reasons": []}
    s = s_max = 0.0
    eq = peak = dd = 0.0
    for r in rs:
        s = max(0.0, s + p["k"] - r)
        s_max = max(s_max, s)
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    mean = sum(rs) / n
    reasons, status = [], "OK"

    def raise_to(level: str, why: str):
        nonlocal status
        reasons.append(why)
        if LEVEL[level] > LEVEL[status]:
            status = level
    if s > p["h_alarm"]:
        raise_to("ALARM", f"CUSUM {s:.1f} > {p['h_alarm']}")
    elif s > p["h_warn"]:
        raise_to("WARN", f"CUSUM {s:.1f} > {p['h_warn']}")
    dd99, dd95 = dd_limit(p["drawdown"], n, "p99"), dd_limit(p["drawdown"], n, "p95")
    if dd > dd99:
        raise_to("ALARM", f"sụt {dd:.1f}R > {dd99:.1f}R (p99 nghiên cứu)")
    elif dd > dd95:
        raise_to("WARN", f"sụt {dd:.1f}R > {dd95:.1f}R (p95 nghiên cứu)")
    upper = mean + 1.2816 * p["sd"] / math.sqrt(n)
    if n >= MIN_MEAN_TEST and upper < 0:
        raise_to("ALARM", f"cận trên 90% của R trung bình {upper:+.2f} < 0")
    return {"n": n, "mean": mean, "total": sum(rs), "cusum": s, "cusum_max": s_max, "drawdown": dd,
            "research_mean": p["mean"], "status": status, "reasons": reasons}


def _s06b_real(trades: list[dict]) -> tuple[list[float], list[float]]:
    """Real S06B SWING results since S06B_START_UTC: (first entries alone, first entry + its add), exit order.

    The add's realized_r is in units of its own risk. The research r_add adds the add's money at the same
    risk unit, so the sum of the two R values is the matching measure. A signal whose add is still open
    (row present, not realized_known) is skipped until it closes."""
    legs = [t for t in trades if t.get("setup") == "S06B" and t.get("profile") == "SWING"]
    adds = {str(t.get("candidate_id")): t for t in legs if str(t.get("candidate_id", "")).endswith(ADD_SUFFIX)}
    firsts = sorted((t for t in legs if not str(t.get("candidate_id", "")).endswith(ADD_SUFFIX)
                     and t.get("realized_known") and t.get("realized_r") is not None
                     and int(t.get("exit_utc") or 0) >= S06B_START_UTC),
                    key=lambda t: int(t.get("exit_utc") or 0))
    alone, with_add = [], []
    for t in firsts:
        r = float(t["realized_r"])
        alone.append(r)
        add = adds.get(str(t.get("candidate_id")) + ADD_SUFFIX)
        if add is None:
            with_add.append(r)
        elif add.get("realized_known") and add.get("realized_r") is not None:
            with_add.append(r + float(add["realized_r"]))
    return alone, with_add


def streams(trades: list[dict], evaluated: list[dict]) -> dict[str, tuple[str, list[float]]]:
    """name -> (params key, results in time order)."""
    real = sorted((t for t in trades if t.get("setup") == "S04" and t.get("profile") == "SWING"
                   and t.get("realized_known") and t.get("realized_r") is not None),
                  key=lambda t: int(t.get("exit_utc") or 0))
    s06b_real, s06b_real_add = _s06b_real(trades)
    ok = [e for e in evaluated if e.get("status") == "EVALUATED"]
    ok.sort(key=lambda e: e["time"])
    s04 = [e["r"] for e in ok if e["setup"] == "S04" and e["profile"] == "SWING"]
    s06 = [e for e in ok if e["setup"] == "S06B" and e["profile"] == "SWING" and e.get("usd") == "ALIGNED"]
    t2_rows = [e for e in ok if e["setup"] == "T2" and e["profile"] == "POSITION" and e["time"] >= T2_START_UTC]
    t2 = [e["r"] for e in t2_rows]
    t2_trend_rows = [e for e in t2_rows if e["symbol"] in TREND_ASSETS]
    t2_trend = [e["r"] for e in t2_trend_rows]
    return {
        "S04_SWING thật": ("S04_SWING", [float(t["realized_r"]) for t in real]),
        "S06B_SWING thật": ("S06B_SWING_USD", s06b_real),
        "S06B_SWING thật + bồi": ("S06B_SWING_USD_ADD", s06b_real_add),
        "S04_SWING ảo": ("S04_SWING", s04),
        "S06B_SWING ảo lọc USD": ("S06B_SWING_USD", [e["r"] for e in s06]),
        "S06B_SWING ảo lọc USD + bồi": ("S06B_SWING_USD_ADD", [e.get("r_add", e["r"]) for e in s06]),
        "T2_POSITION ảo": ("T2_POSITION", t2),
        "T2_POSITION ảo XAU+BTC": ("T2_POSITION_TREND", t2_trend),
        "T2_POSITION ảo XAU+BTC + bồi": ("T2_POSITION_TREND_ADD", [e.get("r_add", e["r"]) for e in t2_trend_rows]),
    }


def run(trades: list[dict], evaluated: list[dict], params: dict) -> dict:
    out = {}
    for name, (key, rs) in streams(trades, evaluated).items():
        out[name] = dict(check(rs, params[key]), params=key)
    return out


def text(result: dict, generated_utc: int) -> str:
    icon = {"NO_DATA": "·", "OK": "OK", "WARN": "CẢNH BÁO", "ALARM": "BÁO ĐỘNG"}
    lines = [f"Theo dõi lợi thế (từ {datetime.fromtimestamp(START_UTC, timezone.utc):%Y-%m-%d}, "
             f"lúc {datetime.fromtimestamp(generated_utc, timezone.utc):%Y-%m-%d %H:%M} UTC)"]
    for name, r in result.items():
        if r["status"] == "NO_DATA":
            lines.append(f"{icon['NO_DATA']} {name}: chưa có lệnh")
            continue
        lines.append(f"{icon[r['status']]} {name}: {r['n']} lệnh, TB {r['mean']:+.2f}R (nghiên cứu {r['research_mean']:+.2f}R), "
                     f"tổng {r['total']:+.1f}R, sụt {r['drawdown']:.1f}R, CUSUM {r['cusum']:.1f}"
                     + (f" — {'; '.join(r['reasons'])}" if r["reasons"] else ""))
    if any(r["status"] == "ALARM" for r in result.values()):
        lines.append("Đề xuất: chuyển setup báo động về SHADOW và xem lại (/week), không tăng rủi ro.")
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    import weekly_review as wr
    now = int(datetime.now(timezone.utc).timestamp())
    trades = wr.load_trades(wr.trades_path(), START_UTC, now + 86400)
    rows = ce.load(ce.ledger_path(), START_UTC)
    evaluated = ce.evaluate_rows(rows)
    result = run(trades, evaluated, load_params())
    out = context.DATA.parent / "current" / "edge_monitor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": "edge-monitor-v1", "generated_utc": now, "start_utc": START_UTC,
                               "streams": result}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    print(text(result, now))


if __name__ == "__main__":
    main(sys.argv[1:])
