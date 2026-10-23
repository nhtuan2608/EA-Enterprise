#!/usr/bin/env python3
"""EnterpriseEA MCP server (stdio, JSON-RPC 2.0, one message per line). Standard library only.

Lets Claude Code (or any MCP client) look at a running EnterpriseEA through its data folder
MQL5/Files/EnterpriseEA, on this machine or on a VPS over SSH:

    claude mcp add eea-demo -- python bridge/eea_mcp_server.py --root "<terminal>/MQL5/Files/EnterpriseEA"
    claude mcp add eea-vps  -- ssh <user>@<vps> python C:/EEA/bridge/eea_mcp_server.py --root "<...>/MQL5/Files/EnterpriseEA"

Read-only tools (always): bots_status, account_status, read_bot_log, read_audit, vhedge_groups, health_check.
Control tools (only with --allow-control): bot_off, bot_on, bot_confirm, all_bots_off. They write the same
bot command files the Telegram gateway writes, with source "MCP"; the EA checks and applies them
(Bots/BotHost.mqh). The server never sends orders and never touches positions.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bot_journal  # noqa: E402

SERVER_NAME = "enterprise-ea"
SERVER_VERSION = "1.0.0"
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAX_TEXT = 60_000
STATUS_STALE = 120          # bots_status.json / live_status.json are rewritten on every EA timer (30 s)
BOT_CODES = bot_journal.BOTS


def read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def dump(obj) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=1)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "\n... (cắt bớt)"


def tail_lines(path: Path, max_bytes: int = 4_000_000) -> list[str]:
    """Last lines of a big append-only file (audit.jsonl grows to many MB)."""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()                  # drop the partial first line
            data = f.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()


def iso_to_epoch(text: str) -> int:
    try:
        return calendar.timegm(time.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OverflowError):
        return 0


class ToolError(Exception):
    pass


class EeaMcp:
    def __init__(self, root: Path, files_root: Path | None = None, allow_control: bool = False, clock=time.time,
                 operator: str = "mcp"):
        self.root = Path(root)
        self.operator = operator or "mcp"
        self.files_root = Path(files_root) if files_root else self.root.parent
        self.allow_control = allow_control
        self.clock = clock
        self.tools = self._tools()

    def now(self) -> int:
        return int(self.clock())

    # ------------------------------------------------------------------ protocol
    def handle(self, msg: dict) -> dict | None:
        if not isinstance(msg, dict):
            return self.error(None, -32600, "Invalid Request")
        mid, method = msg.get("id"), msg.get("method")
        if mid is None:                       # notification (initialized, cancelled...): no answer
            return None
        params = msg.get("params") or {}
        try:
            if method == "initialize":
                asked = str(params.get("protocolVersion", ""))
                return self.result(mid, {
                    "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": ("EnterpriseEA (MT5) bots host. Start with health_check or bots_status; "
                                     "read_bot_log explains what each bot did and why. Times: at_utc is UTC, "
                                     "'server' is the broker server time shown on the chart."
                                     + (" Control tools switch bots only (bot_on needs bot_confirm)."
                                        if self.allow_control else " Read-only.")),
                })
            if method == "ping":
                return self.result(mid, {})
            if method == "tools/list":
                return self.result(mid, {"tools": [{"name": n, "description": t["description"],
                                                    "inputSchema": t["schema"]} for n, t in self.tools.items()]})
            if method == "tools/call":
                name = params.get("name")
                tool = self.tools.get(name)
                if tool is None:
                    return self.error(mid, -32602, f"Unknown tool: {name}")
                try:
                    text = tool["handler"](params.get("arguments") or {})
                    return self.result(mid, {"content": [{"type": "text", "text": text}], "isError": False})
                except ToolError as exc:
                    return self.result(mid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
            return self.error(mid, -32601, f"Method not found: {method}")
        except Exception as exc:  # never kill the server on one bad call
            return self.error(mid, -32603, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def result(mid, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    @staticmethod
    def error(mid, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    # ------------------------------------------------------------------ tools
    def _tools(self) -> dict:
        bot_prop = {"type": "string", "description": "S07 | VHEDGE | XRT | CTXLIMIT (empty = all bots); read_bot_log also SQZ | W1 (SHADOW candidates)"}
        t = {
            "health_check": {
                "description": "Is the EA alive and are its files where they should be? Checks every expected file "
                               "and folder of the data root (age, size), the live session, the kill switch and stuck "
                               "bot commands. Use first.",
                "schema": {"type": "object", "properties": {}},
                "handler": self.tool_health},
            "bots_status": {
                "description": "Current state of the 4 bots (current/bots_status.json, rewritten every EA timer, 30 s): Active "
                               "flag, mode OFF/SHADOW/LIVE, open positions, P/L today, status line, closeness to the "
                               "next entry, and the portfolio guard (armed, pause, open risk, daily loss).",
                "schema": {"type": "object", "properties": {}},
                "handler": self.tool_bots_status},
            "account_status": {
                "description": "Account and EA safety state: balance/equity, live session (status, expiry, limits), "
                               "kill switch, operator pause, execution armed, risk policy, today's closed P/L.",
                "schema": {"type": "object", "properties": {}},
                "handler": self.tool_account},
            "read_bot_log": {
                "description": "Bots journal (logs/bots-YYYYMM.jsonl): what each bot did and why - DECISION, ENTRY, "
                               "ORDER, MANAGE, EXIT, BLOCKED, SKIP, ERROR, NEAR, FILL, CLOSE, SWITCH, START. Returns a "
                               "per-bot summary (entries, exits, SHADOW R, LIVE money, block reasons) and the lines.",
                "schema": {"type": "object", "properties": {
                    "bot": bot_prop,
                    "hours": {"type": "integer", "minimum": 1, "maximum": 744, "default": 24},
                    "events": {"type": "array", "items": {"type": "string", "enum": list(bot_journal.EVENTS)},
                               "description": "only these events (default: all except NEAR)"},
                    "include_near": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
                    "summary_only": {"type": "boolean", "default": False}}},
                "handler": self.tool_bot_log},
            "read_audit": {
                "description": "EA audit events (logs/audit.jsonl): trades, sessions, bot switches, rejected commands, "
                               "failures. Filter by event type substring.",
                "schema": {"type": "object", "properties": {
                    "hours": {"type": "integer", "minimum": 1, "maximum": 168, "default": 24},
                    "event_type": {"type": "string", "description": "substring, e.g. BOT, TRADE, SESSION, FAIL"},
                    "include_runtime": {"type": "boolean", "default": False,
                                        "description": "also RUNTIME_REFRESHED heartbeats (very many)"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100}}},
                "handler": self.tool_audit},
            "vhedge_groups": {
                "description": "VHedge groups: the open ones (current/bots/vhedge_groups.txt) and the last closed ones "
                               "(MQL5/Files/VHedge_<symbol>_<magic>.csv) with their result in U.",
                "schema": {"type": "object", "properties": {
                    "closed": {"type": "integer", "minimum": 0, "maximum": 200, "default": 20}}},
                "handler": self.tool_vhedge},
        }
        if self.allow_control:
            t.update(self._control_tools(bot_prop))
        return t

    def _control_tools(self, bot_prop) -> dict:
        one = {"type": "object", "properties": {"bot": {**bot_prop, "description": "S07 | VHEDGE | XRT | CTXLIMIT"},
                                                "reason": {"type": "string", "description": "why (kept in the audit)"}},
               "required": ["bot"]}
        return {
            "bot_off": {
                "description": "Switch one bot Inactive at once (no new entries; its open positions keep their "
                               "management). Waits for the EA's answer (applied or rejected, with the reason).",
                "schema": one, "handler": lambda a: self.tool_switch(a, "BOT_DISABLE")},
            "all_bots_off": {
                "description": "Switch every bot Inactive (S07, VHEDGE, XRT, CTXLIMIT). Open positions stay managed.",
                "schema": {"type": "object", "properties": {"reason": {"type": "string"}}},
                "handler": self.tool_all_off},
            "bot_on": {
                "description": "Ask to switch one bot Active. Returns a 6-digit code valid 2 minutes; nothing changes "
                               "until bot_confirm. Only call bot_confirm after the user said yes in the chat.",
                "schema": one, "handler": lambda a: self.tool_switch(a, "BOT_REQUEST_ENABLE")},
            "bot_confirm": {
                "description": "Confirm a bot_on with its code. Call it only after the user explicitly confirmed "
                               "enabling that bot in the conversation.",
                "schema": {"type": "object", "properties": {"bot": one["properties"]["bot"],
                                                            "code": {"type": "string", "pattern": "^[0-9]{6}$"}},
                           "required": ["bot", "code"]},
                "handler": lambda a: self.tool_switch(a, "BOT_CONFIRM_ENABLE")},
        }

    # ------------------------------------------------------------------ control handlers
    COMMAND_TTL = 60
    NONCE_TTL = 115                 # the EA accepts at most 120 s
    RESULT_WAIT = 45.0             # the EA reads commands on its timer (InpRuntimeRefreshSeconds, 30 s)

    def next_sequence(self) -> int:
        """Milliseconds since 1970: above every earlier MCP command, also after a restart (no state file)."""
        seq = int(self.clock() * 1000)
        last = getattr(self, "_last_seq", 0)
        if seq <= last:
            seq = last + 1
        self._last_seq = seq
        return seq

    def write_bot_command(self, action: str, bot: str, nonce: str = "") -> str:
        status = read_json(self.root / "current" / "bots_status.json")
        if not isinstance(status, dict) or not status.get("account_id") or not status.get("state_loaded"):
            raise ToolError("EA chưa sẵn sàng nhận lệnh bot: bots_status.json thiếu hoặc state chưa nạp.")
        age = self.age(status.get("written_at_utc"))
        if age is None or age > STATUS_STALE:
            raise ToolError(f"bots_status.json cũ {age}s: EA không chạy, không gửi lệnh.")
        if status.get("mcp_commands") is False:
            raise ToolError("EA đang tắt lệnh từ MCP (InpBotsMcpCommands=false).")
        seq = self.next_sequence()
        t = self.now()
        command_id = f"mcp-{seq:015d}-{bot.lower()}"
        cmd = {"schema_version": "bot-command-v1.0.0", "command_id": command_id, "action": action, "bot": bot,
               "source": "MCP", "role": "OPERATOR", "chat_id": "mcp", "user_id": self.operator,
               "mcp_sequence": seq, "account_id": status["account_id"],
               "config_version": status.get("config_version", ""), "issued_at_utc": t,
               "expires_at_utc": t + (self.NONCE_TTL if action == "BOT_REQUEST_ENABLE" else self.COMMAND_TTL),
               "confirmation_nonce": nonce,
               "nonce_expires_at_utc": t + self.NONCE_TTL if action == "BOT_REQUEST_ENABLE" else 0}
        d = self.root / "current" / "remote" / "bot_commands"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".{command_id}.tmp"
        # Compact separators: the EA reader (EEA_RiskLedgerField) expects "key":"value" without spaces.
        tmp.write_text(json.dumps(cmd, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, d / f"{command_id}.json")
        return command_id

    def mcp_log(self, command_id: str, action: str, bot: str, reason: str, res: dict | None):
        """The server's own audit: logs/mcp.jsonl (who asked what, why, and the EA's answer). The nonce is not kept."""
        line = {"at_utc": self.now(), "operator": self.operator, "command_id": command_id, "action": action, "bot": bot,
                "reason": reason, "status": (res or {}).get("status", "PENDING"),
                "reason_codes": (res or {}).get("reason_codes")}
        try:
            (self.root / "logs").mkdir(parents=True, exist_ok=True)
            with (self.root / "logs" / "mcp.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def wait_result(self, command_id: str) -> dict | None:
        path = self.root / "current" / "remote" / "results" / f"{command_id}.json"
        deadline = time.monotonic() + self.RESULT_WAIT
        while True:
            data = read_json(path)
            if isinstance(data, dict):
                return data
            if time.monotonic() >= deadline:
                return None
            self.sleep(0.5)

    def sleep(self, seconds: float):
        time.sleep(seconds)

    def tool_switch(self, args, action: str) -> str:
        bot = str(args.get("bot", "")).upper().replace(" ", "")
        if bot not in BOT_CODES:
            raise ToolError(f"bot không hợp lệ: {args.get('bot')} (S07, VHEDGE, XRT, CTXLIMIT)")
        nonce = ""
        if action == "BOT_REQUEST_ENABLE":
            nonce = f"{secrets.randbelow(10 ** 6):06d}"
        elif action == "BOT_CONFIRM_ENABLE":
            nonce = str(args.get("code", ""))
            if len(nonce) != 6 or not nonce.isdigit():
                raise ToolError("code phải là 6 chữ số (từ bot_on)")
        cid = self.write_bot_command(action, bot, nonce)
        res = self.wait_result(cid)
        self.mcp_log(cid, action, bot, str(args.get("reason", ""))[:300], res)
        out = {"command_id": cid, "action": action, "bot": bot}
        if res is None:
            out["status"] = "PENDING"
            out["note"] = f"EA chưa trả lời sau {self.RESULT_WAIT:.0f}s; xem lại bằng bots_status hoặc read_audit."
        else:
            out.update({k: res.get(k) for k in ("status", "applied", "state_before", "state_after", "reason_codes")})
        if action == "BOT_REQUEST_ENABLE" and res and "BOT_ENABLE_CONFIRMATION_PENDING" in (res.get("reason_codes") or []):
            out["code"] = nonce
            out["next"] = (f"Hỏi người dùng có chắc bật {bot} không; chỉ khi họ đồng ý mới gọi "
                           f"bot_confirm(bot='{bot}', code='{nonce}') trong {self.NONCE_TTL} giây.")
        return dump(out)

    def tool_all_off(self, args) -> str:
        results = []
        for bot in BOT_CODES:
            try:
                results.append(json.loads(self.tool_switch({"bot": bot, "reason": args.get("reason", "")}, "BOT_DISABLE")))
            except ToolError as exc:
                results.append({"bot": bot, "status": "NOT_SENT", "error": str(exc)})
        return dump({"results": results})

    # ------------------------------------------------------------------ read-only handlers
    def age(self, written) -> int | None:
        try:
            return self.now() - int(written)
        except (TypeError, ValueError):
            return None

    def tool_bots_status(self, args) -> str:
        data = read_json(self.root / "current" / "bots_status.json")
        if not isinstance(data, dict):
            raise ToolError("Không có current/bots_status.json: EA chưa chạy bản có lớp Bots, InpBotsEnabled=false, "
                            "hoặc --root sai thư mục (cần .../MQL5/Files/EnterpriseEA).")
        age = self.age(data.get("written_at_utc"))
        head = {"age_seconds": age, "stale": age is None or age > STATUS_STALE}
        return dump({**head, **data})

    def tool_account(self, args) -> str:
        cur = self.root / "current"
        snap = read_json(cur / "account_snapshot.json") or {}
        live = read_json(cur / "live_status.json") or {}
        sess = read_json(cur / "live_session.json") or {}
        kill = read_json(cur / "execution_controller_state.json") or {}
        op = read_json(cur / "operator_mode.json") or {}
        stats = read_json(cur / "daily_stats.json") or {}
        out = {
            "account": {k: snap.get(k) for k in ("broker_server", "account_currency", "account_margin_mode", "balance",
                                                 "equity", "margin", "margin_free", "observed_at_utc")},
            "ea": {k: live.get(k) for k in ("execution_enabled", "observer_only", "live_trade_armed", "live_path_armed",
                                            "session", "operator_paused", "recovery_blocked", "last_reason", "modes",
                                            "strategy_running", "risk")},
            "ea_status_age_seconds": self.age(live.get("written_at_utc")),
            "live_session": {k: sess.get(k) for k in ("status", "session_id", "risk_policy_id", "allowed_symbols",
                                                      "valid_until_utc", "max_risk_per_trade_fraction",
                                                      "max_daily_loss_fraction", "real_account")},
            "kill_switch_active": kill.get("kill_active"),
            "operator_mode": {k: op.get(k) for k in ("mode", "operator_paused", "reason")},
        }
        if sess.get("valid_until_utc"):
            out["live_session"]["expires_in_hours"] = round((int(sess["valid_until_utc"]) - self.now()) / 3600, 1)
        days = stats.get("days") or []
        if days:
            d = days[-1]
            out["closed_today"] = {"day": d[0], "pnl": d[1] if len(d) > 1 else None, "trades": d[2] if len(d) > 2 else None,
                                   "row": d}
        return dump(out)

    def tool_bot_log(self, args) -> str:
        hours = max(1, min(744, int(args.get("hours", 24) or 24)))
        bot = str(args.get("bot", "") or "").upper()
        if bot and bot not in bot_journal.JOURNAL_BOTS:
            raise ToolError(f"bot không hợp lệ: {bot} (S07, VHEDGE, XRT, CTXLIMIT, SQZ, W1)")
        limit = max(1, min(1000, int(args.get("limit", 200) or 200)))
        now = self.now()
        entries = bot_journal.read_journal(self.root, now - hours * 3600, now + 60, bot)
        summary = bot_journal.summarize(entries)
        events = tuple(args.get("events") or ())
        if events:
            shown = [e for e in entries if e.get("event") in events]
        elif args.get("include_near"):
            shown = entries
        else:
            shown = [e for e in entries if e.get("event") != "NEAR"]
        out = {"file": f"logs/bots-YYYYMM.jsonl under {self.root}", "hours": hours, "bot": bot or "ALL",
               "summary": summary}
        if not entries:
            out["note"] = ("Chưa có dòng nào: EA chưa chạy bản có nhật ký bot, chưa có sự kiện, "
                           "hoặc --root sai thư mục.")
        if not args.get("summary_only"):
            out["lines"] = shown[-limit:]
            out["lines_omitted"] = max(0, len(shown) - limit)
        return dump(out)

    def tool_audit(self, args) -> str:
        hours = max(1, min(168, int(args.get("hours", 24) or 24)))
        limit = max(1, min(500, int(args.get("limit", 100) or 100)))
        needle = str(args.get("event_type", "") or "").upper()
        since = self.now() - hours * 3600
        out = []
        for line in tail_lines(self.root / "logs" / "audit.jsonl"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            et = str(e.get("event_type", ""))
            if not args.get("include_runtime") and et == "RUNTIME_REFRESHED":
                continue
            if needle and needle not in et.upper():
                continue
            if iso_to_epoch(e.get("occurred_at_utc", "")) < since:
                continue
            out.append({k: e.get(k) for k in ("occurred_at_utc", "event_type", "symbol", "entity_id", "state_before",
                                              "state_after", "reason_codes", "source", "details")})
        return dump({"hours": hours, "count": len(out), "events": out[-limit:]})

    def tool_vhedge(self, args) -> str:
        closed_n = max(0, min(200, int(args.get("closed", 20) or 0)))
        open_groups, sym, magic = [], "", ""
        path = self.root / "current" / "bots" / "vhedge_groups.txt"
        try:
            lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            lines = []
        if lines:
            head = lines[0].split("|")
            if len(head) >= 4:
                sym, magic = head[2], head[3]
            for line in lines[1:]:
                f = line.split("|")
                if len(f) < 45 or f[0] != "G":
                    continue
                legs = []
                for k in range(3):
                    b = 21 + 8 * k
                    if f[b] == "1":
                        legs.append({"leg": ("BUY", "SELL", "ADD")[k], "dir": int(f[b + 1]), "entry": float(f[b + 2]),
                                     "sl": float(f[b + 3]), "lots": float(f[b + 4]), "ticket": f[b + 6]})
                open_groups.append({"id": int(f[1]), "profile": ("G119", "BIGV", "ALL")[int(f[2])] if f[2] in "012" else f[2],
                                    "opened": time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(f[5]))),
                                    "phase": "hedge" if f[7] == "1" else "resolved", "dir": int(f[8]),
                                    "tp": float(f[14]), "be_done": f[15] == "1", "live": f[19] == "1", "note": f[20],
                                    "open_legs": legs})
        closed = []
        csvs = sorted(self.files_root.glob(f"VHedge_{sym or '*'}_{magic or '*'}.csv"))
        for csv in csvs[-1:]:
            rows = tail_lines(csv, 400_000)
            header = None
            for row in rows:
                cells = row.split(";")
                if cells and cells[0] == "mode":
                    header = cells
                    continue
                if len(cells) >= 19:
                    closed.append(dict(zip(header or ["mode", "profile", "group", "v_time", "signal_time", "open_time",
                                                      "close_time", "side", "U", "atr", "buy_entry", "sell_entry",
                                                      "buy_sl", "sell_sl", "add_entry", "tp", "result_price",
                                                      "result_U", "note"], cells)))
        closed = [c for c in closed if c.get("mode") in ("LIVE", "SHADOW")][-closed_n:] if closed_n else []
        total_u = round(sum(float(c.get("result_U", 0) or 0) for c in closed), 2)
        return dump({"open_groups": open_groups, "closed_recent": closed, "closed_recent_sum_U": total_u,
                     "csv": [str(c) for c in csvs[-1:]]})

    def tool_health(self, args) -> str:
        now = self.now()
        checks = []

        def item(rel, max_age=None, kind="file", note=""):
            p = self.root / rel
            ok = p.is_dir() if kind == "dir" else p.is_file()
            row = {"path": rel, "exists": ok, "note": note}
            if ok and kind == "file":
                st = p.stat()
                row["size"] = st.st_size
                row["age_seconds"] = int(now - st.st_mtime)
                row["status"] = "OK" if max_age is None or row["age_seconds"] <= max_age else "STALE"
            else:
                row["status"] = "OK" if ok else "MISSING"
            checks.append(row)
            return row

        item("current/bots_status.json", STATUS_STALE, note="EA timer, every 30 s")
        item("current/bots_state.json", note="Active flags (written on change)")
        item("current/live_status.json", STATUS_STALE, note="EA timer")
        item("current/live_session.json", note="signed live session")
        item("current/execution_controller_state.json", note="kill switch")
        item("current/policy_settings.json", note="risk policy")
        item("current/bots", kind="dir", note="VHedge groups / XauRegime state (created on first save)")
        item("logs/audit.jsonl", 24 * 3600, note="EA audit")
        g = time.gmtime(now)
        item(f"logs/bots-{g.tm_year:04d}{g.tm_mon:02d}.jsonl", 3 * 3600,
             note="bots journal, a NEAR line every M30 bar while the market is open")
        cmd_dir = self.root / "current" / "remote" / "bot_commands"
        waiting = sorted(cmd_dir.glob("*.json")) if cmd_dir.is_dir() else []
        stuck = [p.name for p in waiting if now - p.stat().st_mtime > 30]
        sess = read_json(self.root / "current" / "live_session.json") or {}
        kill = read_json(self.root / "current" / "execution_controller_state.json") or {}
        bots = read_json(self.root / "current" / "bots_status.json") or {}
        problems = [f"{c['path']}: {c['status']}" for c in checks if c["status"] != "OK"]
        if stuck:
            problems.append(f"{len(stuck)} lệnh bot chờ > 30 s chưa được EA xử lý (EA dừng hoặc khác --root?)")
        if sess and sess.get("status") != "ACTIVE":
            problems.append(f"live session {sess.get('status')}")
        elif sess.get("valid_until_utc") and int(sess["valid_until_utc"]) - now < 24 * 3600:
            problems.append("live session hết hạn trong < 24 giờ")
        if kill.get("kill_active"):
            problems.append("kill switch đang BẬT")
        if bots and not bots.get("state_loaded"):
            problems.append(f"bots state chưa nạp: {bots.get('state_reason')}")
        return dump({"root": str(self.root), "root_exists": self.root.is_dir(), "ok": not problems and self.root.is_dir(),
                     "problems": problems, "checks": checks, "bot_commands_waiting": [p.name for p in waiting],
                     "control_tools": self.allow_control})


# ---------------------------------------------------------------------- stdio loop
def serve(server: EeaMcp, stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    for raw in stdin:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = EeaMcp.error(None, -32700, "Parse error")
        else:
            if isinstance(msg, list):         # batch (older clients)
                replies = [r for r in (server.handle(m) for m in msg) if r is not None]
                reply = replies or None
            else:
                reply = server.handle(msg)
        if reply is not None:
            stdout.write((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))
            stdout.flush()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", default=os.environ.get("EEA_ROOT", ""),
                    help="EnterpriseEA data root: <terminal data folder>/MQL5/Files/EnterpriseEA (or env EEA_ROOT)")
    ap.add_argument("--files-root", default="", help="MQL5/Files (default: the parent of --root)")
    ap.add_argument("--allow-control", action="store_true", help="also list the bot switch tools")
    ap.add_argument("--operator", default=os.environ.get("EEA_MCP_OPERATOR", "mcp"),
                    help="name written as user_id in the commands and the audit (e.g. claude-laptop)")
    a = ap.parse_args(argv)
    if not a.root:
        print("eea_mcp_server: --root (or EEA_ROOT) is required", file=sys.stderr)
        return 2
    root = Path(a.root)
    if not root.is_dir():
        print(f"eea_mcp_server: warning, {root} does not exist (tools will say so)", file=sys.stderr)
    serve(EeaMcp(root, Path(a.files_root) if a.files_root else None, a.allow_control, operator=a.operator))
    return 0


if __name__ == "__main__":
    sys.exit(main())
