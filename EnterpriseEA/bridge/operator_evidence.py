"""Evidence for a free-text operator question on Telegram (20/10/2026).

The operator asks in plain words ("sáng giờ có lệnh nào không, sao không vào được?"). The gateway
does not try to guess which file holds the answer: it sends the AI one compact, read-only bundle of
the last hours and the AI answers from it. Everything here only reads files the EA, the bots and
MT5 already write; it never writes, and the bundle is data for the AI, never instructions.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

MAX_BYTES = 40_000              # the bridge accepts 50 KB per request
AUDIT_TAIL_BYTES = 4_000_000    # audit.jsonl grows; the window is in its tail
TRADE_EVENT = re.compile(r"^(TRADE_|ENTRY_|EXECUTION_|ORDER_|LIVE_SESSION_|REMOTE_COMMAND_|BOT_|EA_STOPPED$|"
                         r"EA_INITIALIZED$|OPERATOR_MODE_)|_SHADOW_CANDIDATE$")
LOG_KEEP = re.compile(r"fail|error|invalid|reject|no money|not enough|margin|volume|market closed|disabled|"
                      r"retcode|requote|off quotes|trade|deal|order|position|skipped|blocked|loaded|removed|"
                      r"initialized|crash|exception", re.I)
SHADOW_KEYS = ("setup", "symbol", "profile", "direction", "entry_mode", "entry", "sl", "tp", "volume", "risk_fraction",
               "sentiment", "news_block", "usd_alignment", "dxy_f3", "plan_reason")


def local(ts) -> str:
    try:
        return time.strftime("%H:%M %d/%m", time.localtime(int(ts)))
    except (TypeError, ValueError, OverflowError):
        return ""


def iso_utc(text: str) -> int:
    try:
        return int(time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone)
    except (TypeError, ValueError, OverflowError):
        return 0


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def read_jsonl(path: Path, tail_bytes: int = 0) -> list[dict]:
    try:
        with open(path, "rb") as fh:
            if tail_bytes:
                fh.seek(0, 2)
                fh.seek(max(0, fh.tell() - tail_bytes))
            raw = fh.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for line in raw.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def mt5_log(path: Path, limit: int) -> list[str]:
    """Notable lines of an MT5 log (UTF-16), bot NEAR lines left out, newest last, prefixed dd/mm."""
    try:
        raw = path.read_bytes()
    except OSError:
        return []
    text = raw.decode("utf-16", "replace") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8", "replace")
    keep = []
    for line in text.splitlines():
        parts = line.split("\t")
        body = " ".join(p for p in parts[2:] if p).strip() if len(parts) >= 3 else line.strip()
        if body and " NEAR" not in body and LOG_KEEP.search(body):
            keep.append(f"{path.stem[6:8]}/{path.stem[4:6]} {body}"[:240])
    return keep[-limit:]


def collect(root: Path, now: int, hours: int = 24, terminal: Path | None = None) -> dict:
    """The read-only bundle for one question about the last `hours`."""
    root = Path(root)
    if terminal is None:                             # <terminal>/MQL5/Files/EnterpriseEA
        terminal = root.parents[2] if len(root.parents) > 2 else root
    since = now - hours * 3600
    cur = root / "current"
    live = read_json(cur / "live_status.json") or {}
    account = read_json(cur / "account_snapshot.json") or {}
    recon = read_json(cur / "broker_reconciliation.json") or {}
    session = read_json(cur / "live_session.json") or {}
    bots = read_json(cur / "bots_status.json") or {}
    written = int(live.get("written_at_utc", 0) or 0)
    data = {
        "now_local": local(now), "window_hours": hours,
        "times": "HH:MM dd/mm theo giờ máy VPS; riêng mt5_experts_log và mt5_journal theo giờ UTC (MT5 trong Docker)",
        "ea": {"status_age_s": now - written if written else None, "running": bool(written and now - written <= 300),
               **{k: live.get(k) for k in ("execution_enabled", "observer_only", "live_trade_armed", "session",
                                           "operator_paused", "last_reason", "strategy_running", "strategy_reason",
                                           "runtime_state", "runtime_reason", "modes", "risk")}},
        "account": {k: account.get(k) for k in ("balance", "equity", "margin_free", "currency") if k in account},
        "broker": {"positions": recon.get("position_count"), "orders": recon.get("order_count"),
                   "deals_in_lookback": recon.get("deal_count")},
        "session": {"status": session.get("status"), "until": local(session.get("valid_until_utc")),
                    "symbols": session.get("allowed_symbols")},
        "bots": [{k: b.get(k) for k in ("code", "active", "mode", "open", "today", "status", "near_text")}
                 for b in bots.get("bots", [])],
        "bot_guard": bots.get("guard"),
        # canonical -> broker symbol; "" = not offered by this broker (e.g. ETHUSD on Lirunex), which alone
        # makes ea.last_reason LIVE_SYMBOL_UNRESOLVED while the other symbols trade normally.
        "symbols": {x.get("canonical_symbol"): x.get("broker_symbol")
                    for x in (read_json(cur / "symbol_registry.json") or {}).get("symbols", [])},
    }
    trades = [t for t in read_jsonl(root / "logs" / "trades.jsonl") if int(t.get("exit_utc") or 0) >= since]
    data["closed_trades"] = [{"exit": local(t.get("exit_utc")), "symbol": t.get("symbol"), "setup": t.get("setup"),
                              "direction": t.get("direction"), "r": t.get("realized_r"),
                              "money": t.get("realized_money"), "cause": t.get("exit_cause")} for t in trades[-10:]]
    cands = [c for c in read_jsonl(root / "logs" / "candidates.jsonl")
             if int(c.get("closed_utc") or c.get("first_seen_utc") or 0) >= since]
    data["signals"] = [{"seen": local(c.get("first_seen_utc")), "setup": c.get("setup"), "symbol": c.get("symbol"),
                        "tf": c.get("timeframe"), "direction": c.get("direction"), "mode": c.get("mode"),
                        "result": c.get("disposition"), "reason": c.get("reason")} for c in cands[-40:]]
    events, refresh_failed = [], 0
    for e in read_jsonl(root / "logs" / "audit.jsonl", AUDIT_TAIL_BYTES):
        at = iso_utc(e.get("occurred_at_utc", ""))
        if at < since:
            continue
        kind = str(e.get("event_type", ""))
        if kind == "RUNTIME_REFRESH_FAILED":
            refresh_failed += 1
            continue
        if not TRADE_EVENT.search(kind):
            continue
        row = {"at": local(at), "event": kind, "symbol": e.get("symbol"), "reasons": e.get("reason_codes"),
               "state": e.get("state_after")}
        details = e.get("details") if isinstance(e.get("details"), dict) else {}
        if kind.endswith("_SHADOW_CANDIDATE"):
            row["plan"] = {k: details.get(k) for k in SHADOW_KEYS if k in details}
        elif details:
            row["details"] = json.dumps(details, ensure_ascii=False)[:240]
        events.append(row)
    data["ea_events"] = events[-60:]
    data["runtime_refresh_failed"] = refresh_failed
    journal = []
    for path in sorted((root / "logs").glob("bots-*.jsonl"))[-2:]:
        for j in read_jsonl(path):
            if int(j.get("at_utc", 0) or 0) >= since and j.get("event") != "NEAR":
                journal.append({"at": local(j.get("at_utc")), "bot": j.get("bot"), "event": j.get("event"),
                                "mode": j.get("mode"), "text": str(j.get("text", ""))[:240]})
    data["bot_journal"] = journal[-40:]
    days = sorted({time.strftime("%Y%m%d", time.gmtime(t)) for t in (since, now)})
    data["mt5_experts_log"] = [l for d in days for l in mt5_log(terminal / "MQL5" / "logs" / f"{d}.log", 30)][-30:]
    data["mt5_journal"] = [l for d in days for l in mt5_log(terminal / "logs" / f"{d}.log", 30)][-30:]
    return fit(data)


def fit(data: dict) -> dict:
    """Halve the longest lists until the bundle fits the request budget."""
    lists = ("ea_events", "signals", "bot_journal", "mt5_experts_log", "mt5_journal", "closed_trades")
    while len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
        name = max(lists, key=lambda k: len(json.dumps(data.get(k, []), ensure_ascii=False)))
        if len(data.get(name, [])) <= 1:
            break
        data[name] = data[name][len(data[name]) // 2:]           # keep the newest half
    return data
