"""G48 signal parity: does the live EA emit the candidates the research generators find on the same bars?

  python signal_parity.py                      # since the default start of each setup
  python signal_parity.py --since 2026-10-05

For S04 SWING, S06B SWING (H1) and T2 POSITION (H4, G44 momentum filter) the research generators run on the
bars the EA exported (<data root>/research/bars_*.csv): replay.candidates (S04), setups.s06 with the S06B set
(G23/G27), Tests/t2_oracle.run with momentum=True (T2, D1 closes from the exported H1 bars by server day).
They are compared with logs/candidates.jsonl by (setup, symbol, direction, bar time):
  MATCH       both
  EA_MISSED   research only, the EA was running when the bar closed  -> a code / data difference to explain
  EA_OFFLINE  research only, no runtime refresh within 10 minutes of the bar close (PC off, EA removed)
  EA_EXTRA    EA only                                               -> a code / data difference to explain
Also the EA's historical replay (logs/setup_replay.jsonl, S02/S04 by the MQL engines) against the research on
the same bars. Only bars inside the exported range count (the EA exports again on Saturdays). Writes
<data root>/current/signal_parity.json and prints a short text for /week. Read-only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import candidates_eval as ce
import context
import replay
import setups

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "long"))
sys.path.insert(0, str(HERE.parents[1] / "Tests"))
import t2_oracle  # noqa: E402

START = {"S04": int(datetime(2026, 10, 5, tzinfo=timezone.utc).timestamp()),        # G18 candidate ledger
         "S06B": int(datetime(2026, 10, 6, tzinfo=timezone.utc).timestamp()),       # G29 S06B fields
         "T2": int(datetime(2026, 10, 6, 16, 36, tzinfo=timezone.utc).timestamp())}  # G44 momentum filter
PROFILE = {"S04": "SWING", "S06B": "SWING", "T2": "POSITION"}
TF_SECONDS = {"SWING": 3600, "POSITION": 14400}
S06B = {"box": 24, "max_box_atr": 3.0, "contraction": 0.85, "mode": "immediate", "sl": "far"}   # filters.S06B
OFFLINE_GAP = 600


# ---------------------------------------------------------------------------
# Pure parts (tested)
# ---------------------------------------------------------------------------
def online(at: int, refreshes: list[int]) -> bool:
    """True when a runtime refresh happened within OFFLINE_GAP seconds after `at` (bisect on sorted list)."""
    import bisect
    k = bisect.bisect_left(refreshes, at)
    return k < len(refreshes) and refreshes[k] - at <= OFFLINE_GAP


def compare(research: set, ea: set, close_utc: dict, refreshes: list[int]) -> dict:
    """research / ea: sets of (setup, symbol, direction, bar_time); close_utc: key -> bar close (UTC)."""
    out = {"MATCH": sorted(research & ea), "EA_EXTRA": sorted(ea - research), "EA_MISSED": [], "EA_OFFLINE": []}
    for k in sorted(research - ea):
        out["EA_MISSED" if online(close_utc.get(k, 0), refreshes) else "EA_OFFLINE"].append(k)
    return out


def daily_from_h1(h1: list[dict]) -> list[dict]:
    """Server-day closes from H1 bars (the broker's D1 close is the last H1 close of the server day)."""
    days: dict[int, dict] = {}
    for b in h1:
        d = b["time"] - b["time"] % 86400
        days[d] = {"time": d, "close": b["close"]}
    return [days[k] for k in sorted(days)]


# ---------------------------------------------------------------------------
# Research candidates on the exported bars
# ---------------------------------------------------------------------------
def research_keys(symbol: str, setup: str, start: int) -> tuple[set, dict, int]:
    """Research candidates of one symbol/setup from `start` (UTC); returns keys, close times, last usable bar."""
    keys, close = set(), {}
    m = context.meta()
    now_offset = int(m["server_offset_now"])
    if setup == "T2":
        h4 = context.load_bars(symbol, "H4")
        h1 = context.load_bars(symbol, "H1")
        if len(h4) < 80 or not h1:
            return keys, close, 0
        daily = daily_from_h1(h1)
        first = max(75, next((i for i, b in enumerate(h4) if b["time"] - now_offset >= start), len(h4)))
        for c in t2_oracle.run(h4, daily, first=first, momentum=True):
            b = h4[c["i"]]
            k = ("T2", symbol, c["direction"], b["time"])
            keys.add(k)
            close[k] = b["time"] - now_offset + TF_SECONDS["POSITION"]
        return keys, close, h4[-1]["time"]
    ctx = context.build(symbol, "SWING", ce.FROM_UTC)
    bars = ctx["entry"]
    if setup == "S04":
        cands = replay.candidates(ctx, "S04", replay.engine_params("S04", "SWING"))
    else:
        cands = setups.s06(ctx, S06B)
    for x in cands:
        if x.get("kind") == "LIMIT":
            continue
        b = bars[x["i"]]
        if b["utc"] < start:
            continue
        k = (setup, symbol, int(x["direction"]), b["time"])
        keys.add(k)
        close[k] = b["utc"] + TF_SECONDS["SWING"]
    return keys, close, bars[-1]["time"] if bars else 0


def refresh_times(audit: Path, since: int) -> list[int]:
    out = []
    if not audit.exists():
        return out
    with audit.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"RUNTIME_REFRESHED"' not in line:
                continue
            try:
                t = json.loads(line)["occurred_at_utc"]
            except Exception:
                continue
            u = int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
            if u >= since:
                out.append(u)
    return sorted(out)


def run(since: int | None = None) -> dict:
    rows = ce.load(ce.ledger_path(), 0)
    symbols = sorted({r["symbol"] for r in rows}) or ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
    first = min(START.values()) if since is None else since
    refreshes = refresh_times(context.DATA.parent / "logs" / "audit.jsonl", first - 86400)
    result = {}
    for setup in ("S04", "S06B", "T2"):
        start = START[setup] if since is None else max(since, START[setup])
        research, close, last_bar = set(), {}, {}
        for s in symbols:
            try:
                k, c, lb = research_keys(s, setup, start)
            except Exception as exc:          # a symbol without exported bars must not stop the others
                result.setdefault("errors", []).append(f"{setup} {s}: {exc}")
                continue
            research |= k
            close.update(c)
            last_bar[s] = lb
        ea = {(r["setup"], r["symbol"], int(r["direction"]), int(r["bar_time"])) for r in rows
              if r["setup"] == setup and r["profile"] == PROFILE[setup] and r.get("bar_time")
              and int(r["bar_time"]) <= last_bar.get(r["symbol"], 0) and int(r.get("closed_utc", 0)) >= start - 86400}
        cmp = compare(research, ea, close, refreshes)
        result[setup] = {k: [list(x) for x in v] for k, v in cmp.items()}
        result[setup]["start_utc"] = start
    return result


def replay_parity() -> dict:
    """The EA's own historical replay (logs/setup_replay.jsonl, Runtime/SetupReplay.mqh: the MQL engines over past
    bars) against replay.candidates on the exported bars, per setup and profile, inside the replayed range."""
    path = context.DATA.parent / "logs" / "setup_replay.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = {}
    for setup, profile in sorted({(r["setup"], r["profile"]) for r in rows}):
        ea_rows = [r for r in rows if r["setup"] == setup and r["profile"] == profile]
        lo, hi = min(r["bar_time"] for r in ea_rows), max(r["bar_time"] for r in ea_rows)
        research = set()
        for sym in sorted({r["symbol"] for r in ea_rows}):
            ctx = context.build(sym, profile, ce.FROM_UTC)
            bars = ctx["entry"]
            for x in replay.candidates(ctx, setup, replay.engine_params(setup, profile)):
                t = bars[x["i"]]["time"]
                if x.get("kind") != "LIMIT" and lo <= t <= hi:
                    research.add((sym, int(x["direction"]), t))
        ea = {(r["symbol"], int(r["direction"]), int(r["bar_time"])) for r in ea_rows}
        out[f"{setup} {profile}"] = {"ea": len(ea), "research": len(research), "match": len(ea & research),
                                     "ea_only": sorted(ea - research), "research_only": sorted(research - ea)}
    return out


def text(result: dict) -> str:
    lines = ["Khớp tín hiệu EA ↔ nghiên cứu (trên nến EA xuất):"]
    for setup in ("S04", "S06B", "T2"):
        r = result.get(setup)
        if not r:
            continue
        n = {k: len(r[k]) for k in ("MATCH", "EA_MISSED", "EA_EXTRA", "EA_OFFLINE")}
        total = n["MATCH"] + n["EA_MISSED"] + n["EA_EXTRA"]
        rate = f"{n['MATCH'] / total:.0%}" if total else "chưa có tín hiệu"
        flag = " — CẦN XEM" if n["EA_MISSED"] or n["EA_EXTRA"] else ""
        lines.append(f"{setup}: khớp {n['MATCH']}, EA bỏ sót {n['EA_MISSED']}, EA thừa {n['EA_EXTRA']}, "
                     f"lúc EA tắt {n['EA_OFFLINE']} ({rate}){flag}")
    for key, r in result.get("replay", {}).items():
        lines.append(f"Replay lịch sử của EA {key}: khớp {r['match']}/{max(r['ea'], r['research'])} "
                     f"(EA {r['ea']}, nghiên cứu {r['research']})")
    for e in result.get("errors", []):
        lines.append(f"lỗi: {e}")
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    since = None
    if "--since" in argv:
        since = int(datetime.fromisoformat(argv[argv.index("--since") + 1]).replace(tzinfo=timezone.utc).timestamp())
    result = run(since)
    result["replay"] = replay_parity()
    out = context.DATA.parent / "current" / "signal_parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": "signal-parity-v1", "generated_utc": int(datetime.now(timezone.utc).timestamp()),
                               "result": result}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(out)
    sys.stdout.buffer.write((text(result) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main(sys.argv[1:])
