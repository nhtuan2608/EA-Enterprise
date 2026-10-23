"""Bots host journal reader (logs/bots-YYYYMM.jsonl written by EnterpriseEA Bots/BotJournal.mqh).

Shared by the Telegram gateway (/botlog) and the MCP server (read_bot_log). Standard library only.
Each line: {"at_utc", "server", "bot", "event", "mode", "text", "data"}. The EA only appends; every
summary (per bot: entries, exits, R of SHADOW exits, money of LIVE closes, block reasons) is computed here.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

EVENTS = ("START", "SWITCH", "DECISION", "ENTRY", "ORDER", "MANAGE", "EXIT", "BLOCKED", "SKIP", "ERROR",
          "NEAR", "FILL", "CLOSE")
BOTS = ("S07", "VHEDGE", "XRT", "CTXLIMIT")
SHADOW_ONLY = ("SQZ", "W1")          # G153 research candidates: journal only, no Active flag (Bots/ShadowCandidates.mqh)
JOURNAL_BOTS = BOTS + SHADOW_ONLY


def journal_files(root: Path, since: int, until: int) -> list[Path]:
    """Monthly files (UTC month) that may hold lines between since and until."""
    out = []
    a, b = time.gmtime(max(0, since)), time.gmtime(max(0, until))
    y, m = a.tm_year, a.tm_mon
    while (y, m) <= (b.tm_year, b.tm_mon):
        p = Path(root) / "logs" / f"bots-{y:04d}{m:02d}.jsonl"
        if p.exists():
            out.append(p)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def read_journal(root: Path, since: int, until: int | None = None, bot: str = "",
                 events: tuple[str, ...] | None = None, limit: int = 0) -> list[dict]:
    """Lines between since and until (UTC seconds), oldest first; optional bot / event filters, last `limit` kept."""
    until = int(time.time()) + 60 if until is None else until
    bot = bot.upper()
    out = []
    for path in journal_files(root, since, until):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue          # a line being written, or damaged: skipped
            if not isinstance(e, dict):
                continue
            at = int(e.get("at_utc", 0) or 0)
            if at < since or at > until:
                continue
            if bot and e.get("bot") != bot:
                continue
            if events and e.get("event") not in events:
                continue
            out.append(e)
    out.sort(key=lambda e: int(e.get("at_utc", 0) or 0))
    return out[-limit:] if limit > 0 else out


def summarize(entries: list[dict]) -> dict:
    """Per bot: event counts, SHADOW R, LIVE money, block reasons, last decision / near line, switches."""
    bots: dict[str, dict] = {}
    for e in entries:
        code = str(e.get("bot", ""))
        b = bots.setdefault(code, {"events": {}, "entries": 0, "exits": 0, "shadow_r": 0.0, "shadow_exits": 0,
                                   "live_money": 0.0, "live_closes": 0, "blocked": [], "switches": [],
                                   "last_decision": "", "last_near": "", "last_near_score": None, "errors": 0})
        ev = str(e.get("event", ""))
        b["events"][ev] = b["events"].get(ev, 0) + 1
        data = e.get("data") if isinstance(e.get("data"), dict) else {}
        text = str(e.get("text", ""))
        if ev == "ENTRY" or ev == "FILL":
            b["entries"] += 1
        elif ev == "EXIT":
            b["exits"] += 1
            if e.get("mode") == "SHADOW" and isinstance(data.get("r"), (int, float)):
                b["shadow_r"] += float(data["r"])
                b["shadow_exits"] += 1
            if isinstance(data.get("u"), (int, float)) and e.get("mode") == "SHADOW":
                b["shadow_r"] += float(data["u"])
                b["shadow_exits"] += 1
        elif ev == "CLOSE":
            b["live_closes"] += 1
            if isinstance(data.get("money"), (int, float)):
                b["live_money"] += float(data["money"])
        elif ev == "BLOCKED":
            reason = str(data.get("reason") or text)
            if reason not in b["blocked"]:
                b["blocked"].append(reason)
        elif ev == "SWITCH":
            b["switches"].append(f"{e.get('server', '')} {text}")
        elif ev == "DECISION":
            b["last_decision"] = f"{e.get('server', '')} {text}"
        elif ev == "NEAR":
            b["last_near"] = text
            if isinstance(data.get("score"), (int, float)):
                b["last_near_score"] = float(data["score"])
        elif ev == "ERROR":
            b["errors"] += 1
    for b in bots.values():
        b["shadow_r"] = round(b["shadow_r"], 2)
        b["live_money"] = round(b["live_money"], 2)
    return {"count": len(entries), "bots": bots,
            "first_utc": int(entries[0].get("at_utc", 0)) if entries else None,
            "last_utc": int(entries[-1].get("at_utc", 0)) if entries else None}


NOTABLE = ("START", "SWITCH", "DECISION", "ENTRY", "ORDER", "MANAGE", "EXIT", "BLOCKED", "SKIP", "ERROR", "FILL", "CLOSE")


def journal_text(root: Path, hours: int, bot: str = "", now: int | None = None, max_lines: int = 25,
                 width: int = 170) -> str:
    """Telegram / chat text: per-bot summary of the last `hours`, then the latest notable lines (NEAR left out)."""
    now = int(time.time()) if now is None else now
    entries = read_journal(root, now - hours * 3600, now + 60, bot)
    who = bot or "tất cả bot"
    if not entries:
        return (f"Nhật ký bot ({who}, {hours} giờ): chưa có dòng nào.\n"
                "EA ghi vào logs/bots-YYYYMM.jsonl từ bản có nhật ký bot (16/10/2026).")
    s = summarize(entries)
    lines = [f"Nhật ký bot ({who}, {hours} giờ qua): {s['count']} dòng"]
    for code in JOURNAL_BOTS:
        b = s["bots"].get(code)
        if not b:
            continue
        part = [f"{code}: vào {b['entries']}, thoát {b['exits']}"]
        if b["shadow_exits"]:
            part.append(f"ảo {b['shadow_r']:+.2f}R/U")
        if b["live_closes"]:
            part.append(f"thật {b['live_money']:+.2f}")
        if b["blocked"]:
            part.append("bị chặn: " + ", ".join(b["blocked"][:4]))
        if b["errors"]:
            part.append(f"lỗi {b['errors']}")
        lines.append(" | ".join(part))
        if b["last_near"]:
            sc = b["last_near_score"]
            lines.append(f"   gần khớp{'' if sc is None else f' {round(100 * sc)}%'}: {b['last_near'][:width]}")
    notable = [e for e in entries if e.get("event") in NOTABLE][-max_lines:]
    if notable:
        lines.append("Gần nhất (giờ server):")
        for e in notable:
            lines.append(f"{str(e.get('server', ''))[-5:]} {e.get('bot', '')} {e.get('event', '')}"
                         f"{' ' + str(e.get('mode')) if e.get('mode') else ''}: {str(e.get('text', ''))[:width]}")
    return "\n".join(lines)
