"""G10 offline research: bar loading and per-bar market context (zones, levels, HTF).

The context is independent of the setup parameters, so it is built once per symbol and
profile and cached; parameter variants only re-run the engines. Mirrors
Runtime/SetupReplay.mqh (levels as seen when each entry bar closed).
"""
from __future__ import annotations

import csv
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "Tests"))
import s02_v1_oracle as lv  # noqa: E402

DATA = Path(os.environ.get("EEA_RESEARCH_DATA", r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal"
                           r"\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Files\EnterpriseEA\research"))
CACHE = HERE / ".cache"

ATR_PERIOD = 14
WING = 3
LEVEL_BARS = {"SCALP": 200, "SWING": 320, "SWING4": 320}   # SWING4 (G35): H4 entries, D1 levels
SWING_LOOKBACK = {"SCALP": 120, "SWING": 240, "SWING4": 240}
MIN_LEVEL_BARS = 48
ENTRY_TF = {"SCALP": "M5", "SWING": "H1", "SWING4": "H4"}
LEVEL_TF = {"SCALP": "H1", "SWING": "H4", "SWING4": "D1"}
TF_SECONDS = {"M5": 300, "H1": 3600, "H4": 14400, "D1": 86400}


def load_bars(symbol: str, tf: str) -> list[dict]:
    out = []
    with open(DATA / f"bars_{symbol}_{tf}.csv", newline="") as f:
        for r in csv.DictReader(f):
            out.append({"time": int(r["time"]), "open": float(r["open"]), "high": float(r["high"]),
                        "low": float(r["low"]), "close": float(r["close"]), "spread": int(r["spread"])})
    return out


TIME_RULE = "calendar_now_offset"


def reaction_ok(r: dict) -> bool:
    """G54: a news reaction record measured with the right event time (MT5 calendar times are on today's server
    clock; older lines put US-winter events one hour late). Older lines stay in the log but are not used."""
    return r.get("time_rule") == TIME_RULE


def meta() -> dict:
    m = json.loads((DATA / "bars_meta.json").read_text(encoding="utf-8"))
    m["by_symbol"] = {s["symbol"]: s for s in m["symbols"]}
    return m


def atr_at(bars: list[dict], last: int, period: int = ATR_PERIOD) -> float:
    """Simple-average true range ending at `last` (EEA_StrategyRuntimeAtrFromRates)."""
    if period < 1 or last < period:
        return 0.0
    s = 0.0
    for i in range(last - period + 1, last + 1):
        pc = bars[i - 1]["close"]
        s += max(bars[i]["high"], pc) - min(bars[i]["low"], pc)
    return s / period


def _us_dst(utc: int) -> bool:
    y = datetime.fromtimestamp(utc, timezone.utc).year

    def nth_sunday(month: int, nth: int) -> int:
        first = int(datetime(y, month, 1, tzinfo=timezone.utc).timestamp())
        wd = datetime.fromtimestamp(first, timezone.utc).weekday()  # Monday 0
        offset = (6 - wd) % 7
        return first + (offset + (nth - 1) * 7) * 86400

    return nth_sunday(3, 2) + 7 * 3600 <= utc < nth_sunday(11, 1) + 6 * 3600


def server_offset_at(utc: int, current_offset: int, now_utc: int) -> int:
    winter = current_offset - (3600 if _us_dst(now_utc) else 0)
    return winter + (3600 if _us_dst(utc) else 0)


def levels_from_bars(bars: list[dict], profile: str, now_server: int, offset: int) -> list:
    pts = lv.levels_previous_day(bars, now_server)
    if profile.startswith("SWING"):
        pts += lv.levels_previous_week(bars, now_server)
        pts += lv.levels_swings(bars, WING, SWING_LOOKBACK[profile])
    else:
        pts += lv.levels_session(bars, now_server, offset, 0, 7)
        pts += lv.levels_session(bars, now_server, offset, 7, 12)
        pts += lv.levels_session(bars, now_server, offset, 12, 21)
        pts += lv.levels_swings(bars, WING, SWING_LOOKBACK["SCALP"])
    return pts[:64]


def build(symbol: str, profile: str, from_utc: int) -> dict:
    """Entry bars with ATR plus, per level-bar index, the zones/points/HTF structure."""
    key = CACHE / f"ctx_{symbol}_{profile}_{from_utc}.pkl"
    m = meta()
    csv_mtime = os.path.getmtime(DATA / f"bars_{symbol}_{ENTRY_TF[profile]}.csv")
    if key.exists() and os.path.getmtime(key) > csv_mtime:
        return pickle.loads(key.read_bytes())
    entry = load_bars(symbol, ENTRY_TF[profile])
    level = load_bars(symbol, LEVEL_TF[profile])
    es, ls = TF_SECONDS[ENTRY_TF[profile]], TF_SECONDS[LEVEL_TF[profile]]
    now_offset = int(m["server_offset_now"])
    now_utc = int(m["exported_at_utc"])
    from_server = from_utc + server_offset_at(from_utc, now_offset, now_utc)
    wanted = LEVEL_BARS[profile]
    for i in range(len(entry)):
        entry[i]["atr"] = atr_at(entry, i)
        approx_utc = entry[i]["time"] - now_offset
        entry[i]["utc"] = entry[i]["time"] - server_offset_at(approx_utc, now_offset, now_utc)
    ctx_by_level = {}
    bar_level = []
    li = -1
    for b in entry:
        asof = b["time"] + es
        while li + 1 < len(level) and level[li + 1]["time"] + ls <= asof:
            li += 1
        bar_level.append(li)
        if b["time"] < from_server or li + 1 < MIN_LEVEL_BARS or li in ctx_by_level:
            continue
        window = level[max(0, li + 1 - wanted): li + 1]
        catr = atr_at(level, li)
        offset = server_offset_at(asof - now_offset, now_offset, now_utc)
        pts = levels_from_bars(window, profile, asof, offset)
        zones = lv.build_zones(pts, 0.25 * catr, 0.5 * catr, 2) if catr > 0 else []
        ctx_by_level[li] = {"points": [p[2] for p in pts], "zones": [z for z in zones if z["qualified"]],
                            "structure": lv.htf_structure(window, WING)}
    ctx = {"symbol": symbol, "profile": profile, "from_server": from_server, "entry": entry,
           "bar_level": bar_level, "levels": ctx_by_level, "point": float(m["by_symbol"][symbol]["point"]),
           "digits": int(m["by_symbol"][symbol]["digits"])}
    CACHE.mkdir(exist_ok=True)
    key.write_bytes(pickle.dumps(ctx))
    return ctx
