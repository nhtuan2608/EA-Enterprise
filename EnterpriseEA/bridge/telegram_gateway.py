"""EnterpriseEA Telegram gateway v1 (design 2026-10-05-telegram-gateway-v1, REQ-018..020).

Long polling only (no inbound port). The gateway authenticates the private chat, turns
/pause, /resume and /confirm into remote-mode commands for the EA, /ask into a read-only
ASK_AI request for the AI bridge, and sends back what the EA or the bridge actually decided.
It never trades, never changes EA inputs and never treats an AI answer as a command.

  python telegram_gateway.py --queue-root <MQL5/Files/EnterpriseEA> --config telegram.json --loop

The bot token comes from the EEA_TELEGRAM_TOKEN environment variable or from `token_file`
in the config (outside the repository); it never appears in logs or replies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "telegram-gateway-v1.0.0"
COMMAND_SCHEMA = "remote-command-v1.0.0"
AI_SCHEMA = "1.0"
COMMAND_TTL = 60                # seconds a /pause or /confirm command stays valid for the EA
RESUME_TTL = 120                # REQUEST_RESUME command and nonce lifetime (EA max 120 s)
RESULT_WAIT = 90                # no EA result after this: tell the user the EA did not confirm
ASK_DEADLINE = 180              # AI request deadline for the bridge
ASK_WAIT = 240                  # no AI answer after this: tell the user it timed out
MAX_QUESTION = 300              # the bridge truncates context strings at 300 characters
MAX_MESSAGE = 3500              # Telegram allows 4096
STATUS_STALE = 120              # EA snapshot older than this is reported STALE
NEWS_LEAD = 30 * 60             # notify HIGH events this long before
ALERT_THROTTLE = 15 * 60
SEND_ATTEMPTS = 5

DEFAULT_CONFIG = {
    "operators": [],            # Telegram user ids allowed to pause/resume (private chat)
    "viewers": [],              # user ids allowed /status and /ask
    "token_file": "",
    "poll_timeout": 25,
    "ai_provider": "claude",
    "commands_per_minute": 20,
    "asks_per_hour": 6,
    "notify": {"trades": True, "alerts": True, "ai_reports": True, "news": True},
}

TRADE_EVENTS = {"TRADE_ENTERED": "VÀO LỆNH", "TRADE_MANAGEMENT": "QUẢN LÝ LỆNH",
                "TRADE_EXITED": "ĐÓNG LỆNH", "TRADE_NOT_FILLED": "LỆNH KHÔNG KHỚP"}
ALERT_EVENTS = {"EA_STOPPED", "EA_INITIALIZED", "RUNTIME_REFRESH_FAILED", "LIVE_SESSION_REVOKED",
                "OPERATOR_MODE_FAIL_CLOSED", "EXECUTION_RECOVERY_CONFIRMED", "EXECUTION_RECOVERY_OPERATOR_RESOLVED",
                "TRADE_MANAGER_PERSISTENCE_FAILED"}
ALERT_REASONS = ("LOSS_LIMIT_REACHED", "RECOVERY_REQUIRED", "EXECUTION_UNKNOWN")
REPORT_TYPES = {"EA_DIAGNOSTICS": "Chẩn đoán EA", "NEWS_DATA_REVIEW": "Review dữ liệu tin"}

HELP_VIEWER = ("/status - trạng thái EA\n"
               "/ask <câu hỏi> - hỏi AI (chỉ đọc, không đặt lệnh)\n"
               "/help - danh sách lệnh")
HELP_OPERATOR = HELP_VIEWER + ("\n/pause - dừng vào lệnh mới (vị thế đang có vẫn được quản lý)\n"
                               "/resume - xin bật lại vào lệnh, nhận mã xác nhận\n"
                               "/confirm <mã> - xác nhận bật lại trong 2 phút")


def now() -> int:
    return int(time.time())


# ---------------------------------------------------------------------------
# Telegram API (the only network access; replaced by a fake in tests)
# ---------------------------------------------------------------------------
class TelegramApi:
    def __init__(self, token: str):
        self.token = token

    def call(self, method: str, params: dict, timeout: int = 35) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8", "replace") or "{}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise ConnectionError(str(exc)) from None
        if not body.get("ok"):
            raise ConnectionError(str(body.get("description", "telegram error")))
        return body


def redact(text: str, token: str) -> str:
    text = str(text)
    if token:
        text = text.replace(token, "<token>")
    return re.sub(r"bot\d+:[A-Za-z0-9_\-]{20,}", "bot<token>", text)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def write_atomic(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Compact separators: the EA's MQL reader expects "key":"value" without spaces.
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # The EA or the AI bridge may hold the target open for a moment while reading it (Windows).
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))


def clip(text: str, limit: int = MAX_MESSAGE) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------
class Gateway:
    def __init__(self, root: Path, config: dict, api, token: str = "", clock=now):
        self.root = Path(root)
        self.config = config
        self.api = api
        self.token = token
        self.clock = clock
        self.dir = self.root / "telegram"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.log_path = self.root / "logs" / "telegram.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.operators = {int(x) for x in config.get("operators", [])}
        self.viewers = {int(x) for x in config.get("viewers", [])} - self.operators
        self.state = self._load_state()

    # -- state and log ------------------------------------------------------
    def _load_state(self) -> dict:
        base = {"offset": 0, "sequence": 0, "seen_updates": [], "pending_commands": {}, "pending_asks": {},
                "outbox": [], "audit_pos": 0, "audit_size": 0, "reports_seen": {}, "news_seen": [],
                "alerts_at": {}, "rate": {}, "asks": {}}
        loaded = read_json(self.state_path)
        if isinstance(loaded, dict):
            base.update(loaded)
        return base

    def save(self):
        self.state["seen_updates"] = self.state["seen_updates"][-500:]
        self.state["news_seen"] = self.state["news_seen"][-200:]
        write_atomic(self.state_path, self.state)

    def log(self, event: str, **fields):
        line = {"at_utc": self.clock(), "event": event, **fields}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(redact(json.dumps(line, ensure_ascii=False), self.token) + "\n")

    def next_sequence(self) -> int:
        self.state["sequence"] += 1
        return self.state["sequence"]

    # -- sending ------------------------------------------------------------
    def send(self, chat_id: int, text: str, reply_to: int | None = None):
        self.state["outbox"].append({"chat_id": int(chat_id), "text": clip(redact(text, self.token)),
                                     "reply_to": reply_to, "attempts": 0, "next_at": 0})

    def broadcast(self, text: str):
        for chat in sorted(self.operators | self.viewers):
            self.send(chat, text)

    def flush(self):
        keep = []
        for m in self.state["outbox"]:
            if m["next_at"] > self.clock():
                keep.append(m)
                continue
            params = {"chat_id": m["chat_id"], "text": m["text"], "disable_web_page_preview": True}
            if m.get("reply_to"):
                params["reply_to_message_id"] = m["reply_to"]
                params["allow_sending_without_reply"] = True
            try:
                self.api.call("sendMessage", params, timeout=20)
                self.log("TELEGRAM_DELIVERED", chat_id=m["chat_id"])
            except ConnectionError as exc:
                m["attempts"] += 1
                if m["attempts"] >= SEND_ATTEMPTS:
                    self.log("DELIVERY_FAILED", chat_id=m["chat_id"], detail=redact(exc, self.token)[:200])
                else:
                    m["next_at"] = self.clock() + 2 ** m["attempts"]
                    keep.append(m)
        self.state["outbox"] = keep

    # -- authentication (TC-TG-01) -----------------------------------------
    def role_of(self, msg: dict) -> str | None:
        chat, sender = msg.get("chat", {}), msg.get("from", {})
        if chat.get("type") != "private" or not sender or sender.get("is_bot"):
            return None
        uid = sender.get("id")
        if uid is None or chat.get("id") != uid:
            return None
        if uid in self.operators:
            return "OPERATOR"
        if uid in self.viewers:
            return "VIEWER"
        return None

    def rate_ok(self, uid: int, kind: str, limit: int, window: int) -> bool:
        key = f"{kind}:{uid}"
        stamps = [t for t in self.state["rate"].get(key, []) if t > self.clock() - window]
        if len(stamps) >= limit:
            self.state["rate"][key] = stamps
            return False
        stamps.append(self.clock())
        self.state["rate"][key] = stamps
        return True

    # -- updates ------------------------------------------------------------
    def handle_update(self, update: dict):
        uid_update = int(update.get("update_id", 0))
        self.state["offset"] = max(self.state["offset"], uid_update + 1)
        if uid_update in self.state["seen_updates"]:          # TC-TG-02
            return
        self.state["seen_updates"].append(uid_update)
        msg = update.get("message") or {}
        role = self.role_of(msg)
        if role is None:
            self.log("UNAUTHORIZED", update_id=uid_update, user_id=(msg.get("from") or {}).get("id"),
                     chat_type=(msg.get("chat") or {}).get("type"))
            return
        text = str(msg.get("text", "")).strip()
        uid, mid = msg["from"]["id"], msg.get("message_id")
        if not self.rate_ok(uid, "cmd", self.config["commands_per_minute"], 60):
            self.send(uid, "Quá nhiều lệnh, thử lại sau 1 phút.", mid)
            return
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@", 1)[0].lower()
        self.log("RECEIVED", update_id=uid_update, user_id=uid, role=role, command=cmd[:16])
        if cmd in ("/start", "/help"):
            self.send(uid, HELP_OPERATOR if role == "OPERATOR" else HELP_VIEWER, mid)
        elif cmd == "/status":
            self.send(uid, self.status_text(), mid)
        elif cmd == "/ask":
            self.cmd_ask(uid, mid, arg.strip(), uid_update)
        elif cmd in ("/pause", "/resume", "/confirm"):
            if role != "OPERATOR":
                self.log("UNAUTHORIZED_ACTION", update_id=uid_update, user_id=uid, command=cmd)
                self.send(uid, "Lệnh này chỉ dành cho operator.", mid)
            elif cmd == "/pause":
                self.write_command("PAUSE_ENTRIES", uid, mid, uid_update)
            elif cmd == "/resume":
                nonce = f"{secrets.randbelow(10 ** 6):06d}"
                self.write_command("REQUEST_RESUME", uid, mid, uid_update, nonce=nonce)
            else:
                nonce = arg.strip()
                if not re.fullmatch(r"\d{6}", nonce):
                    self.send(uid, "Cú pháp: /confirm <mã 6 số>", mid)
                else:
                    self.write_command("CONFIRM_RESUME", uid, mid, uid_update, nonce=nonce)
        else:
            self.send(uid, "Chỉ hỗ trợ lệnh. Gõ /help.", mid)

    # -- EA commands (REQ-019) ----------------------------------------------
    def write_command(self, action: str, uid: int, mid, update_id: int, nonce: str = ""):
        mode = read_json(self.root / "current" / "operator_mode.json")
        if not isinstance(mode, dict) or not mode.get("account_id"):
            self.send(uid, "EA chưa sẵn sàng (chưa có operator_mode.json). Kiểm tra EA đã chạy bản có Telegram chưa.", mid)
            return
        seq = self.next_sequence()
        t = self.clock()
        ttl = RESUME_TTL if action == "REQUEST_RESUME" else COMMAND_TTL
        command_id = f"tg-{seq:06d}-{secrets.token_hex(4)}"
        cmd = {"schema_version": COMMAND_SCHEMA, "command_id": command_id, "action": action, "role": "OPERATOR",
               "chat_id": str(uid), "user_id": str(uid), "telegram_update_id": update_id, "gateway_sequence": seq,
               "account_id": mode["account_id"], "config_version": mode.get("config_version", ""),
               "expected_state_version": int(mode.get("state_version", 0)), "issued_at_utc": t,
               "expires_at_utc": t + ttl, "confirmation_nonce": nonce,
               "nonce_expires_at_utc": t + RESUME_TTL - 5 if action == "REQUEST_RESUME" else 0,
               "private_chat_attested": True, "sender_authenticated": True, "source_authenticated": True}
        write_atomic(self.root / "current" / "remote" / "commands" / f"{seq:012d}.json", cmd)
        self.state["pending_commands"][command_id] = {"chat_id": uid, "reply_to": mid, "action": action,
                                                      "issued": t, "nonce": nonce}
        self.log("QUEUED", command_id=command_id, action=action, sequence=seq)
        self.send(uid, f"Đã nhận {action}, chờ EA xác nhận...", mid)

    def poll_results(self):
        results = self.root / "current" / "remote" / "results"
        for command_id, p in list(self.state["pending_commands"].items()):
            path = results / f"{command_id}.json"
            res = read_json(path)
            if isinstance(res, dict):
                reason = ",".join(res.get("reason_codes", []))
                if p["action"] == "REQUEST_RESUME" and res.get("applied"):
                    text = (f"Mã xác nhận: {p['nonce']}\nGửi /confirm {p['nonce']} trong 2 phút để bật lại vào lệnh.\n"
                            "EA sẽ kiểm tra lại toàn bộ điều kiện an toàn trước khi bật.")
                elif res.get("applied"):
                    text = f"EA đã áp dụng {p['action']}: {res.get('state_before')} -> {res.get('state_after')} ({reason})"
                elif res.get("status") == "DUPLICATE_IGNORED":
                    text = f"EA bỏ qua lệnh trùng {p['action']} ({reason}). Trạng thái: {res.get('state_after')}"
                else:
                    text = f"EA từ chối {p['action']}: {reason}. Trạng thái vẫn là {res.get('state_after')}"
                self.send(p["chat_id"], text, p["reply_to"])
                self.log("EA_APPLIED" if res.get("applied") else "EA_REJECTED", command_id=command_id, reason=reason)
                try:
                    path.unlink()
                except OSError:
                    pass
                del self.state["pending_commands"][command_id]
            elif self.clock() - p["issued"] > RESULT_WAIT:
                self.send(p["chat_id"], f"EA chưa xác nhận {p['action']} sau {RESULT_WAIT} giây (EA có thể không chạy). "
                                        "Không có gì thay đổi cho tới khi EA xác nhận.", p["reply_to"])
                self.log("EA_NO_RESULT", command_id=command_id)
                del self.state["pending_commands"][command_id]

    # -- /ask (REQ-020) -----------------------------------------------------
    def cmd_ask(self, uid: int, mid, question: str, update_id: int):
        if not question:
            self.send(uid, "Cú pháp: /ask <câu hỏi>", mid)
            return
        if not self.rate_ok(uid, "ask", self.config["asks_per_hour"], 3600):
            self.send(uid, f"Đã đủ {self.config['asks_per_hour']} câu hỏi trong 1 giờ, thử lại sau.", mid)
            return
        seq = self.next_sequence()
        request_id = f"tg-{seq:06d}-{secrets.token_hex(4)}"
        t = self.clock()
        req = {"schema_version": AI_SCHEMA, "request_id": request_id, "request_type": "ASK_AI",
               "created_at_utc": t, "deadline_utc": t + ASK_DEADLINE, "provider": self.config["ai_provider"],
               "allowed_actions": ["REPORT", "WARN"],
               "context": {"operator_question": question[:MAX_QUESTION], "source": "TELEGRAM",
                           "telegram_update_id": update_id, "snapshot": self.status_data()}}
        write_atomic(self.root / "ai" / "requests" / f"{request_id}.json", req)
        self.state["pending_asks"][request_id] = {"chat_id": uid, "reply_to": mid, "issued": t}
        self.log("QUEUED", request_id=request_id, request_type="ASK_AI")
        self.send(uid, "Đã gửi câu hỏi cho AI, chờ trả lời...", mid)

    def poll_asks(self):
        responses = self.root / "ai" / "responses"
        for request_id, p in list(self.state["pending_asks"].items()):
            path = responses / f"{request_id}.json"
            res = read_json(path)
            if isinstance(res, dict):
                if res.get("status") == "OK":
                    lines = [str(res.get("summary", ""))]
                    lines += [f"[{f.get('severity')}] {f.get('detail')}" for f in res.get("findings", [])]
                    lines += [f"> {r.get('target')}: {r.get('proposal')}" for r in res.get("recommendations", [])]
                    text = "AI (chỉ để tham khảo, không phải lệnh):\n" + "\n".join(l for l in lines if l)
                else:
                    text = f"AI lỗi: {res.get('error', 'UNKNOWN')} {res.get('error_detail', '')}".strip()
                # TC-TG-04: whatever the answer says, it is only text; nothing is queued for the EA.
                self.send(p["chat_id"], text, p["reply_to"])
                self.log("AI_COMPLETED", request_id=request_id, status=res.get("status"))
                try:
                    path.unlink()
                except OSError:
                    pass
                del self.state["pending_asks"][request_id]
            elif self.clock() - p["issued"] > ASK_WAIT:
                self.send(p["chat_id"], "AI chưa trả lời (timeout). Kiểm tra AI Bridge có đang chạy không.", p["reply_to"])
                self.log("AI_TIMEOUT", request_id=request_id)
                del self.state["pending_asks"][request_id]

    # -- /status (TC-TG-08: only what the EA wrote) ---------------------------
    def status_data(self) -> dict:
        cur = self.root / "current"
        mode = read_json(cur / "operator_mode.json") or {}
        runtime = read_json(cur / "runtime_status.json") or {}
        session = read_json(cur / "live_session.json") or {}
        recon = read_json(cur / "broker_reconciliation.json") or {}
        account = read_json(cur / "account_snapshot.json") or {}
        news = read_json(cur / "news_state.json") or {}
        sentiment = read_json(cur / "sentiment.json") or {}
        heartbeat = read_json(self.root / "ai" / "bridge_heartbeat.json") or {}
        age = None
        try:
            observed = time.strptime(runtime.get("observed_at_utc", ""), "%Y-%m-%dT%H:%M:%SZ")
            age = self.clock() - int(time.mktime(observed) - time.timezone)
        except (ValueError, OverflowError):
            pass
        return {
            "operator_mode": mode.get("mode", "UNKNOWN"),
            "runtime_state": runtime.get("runtime_state", "UNKNOWN"),
            "snapshot_age_s": age,
            "stale": age is None or age > STATUS_STALE,
            "session": session.get("status", "NONE"),
            "session_until_utc": session.get("valid_until_utc"),
            "positions": recon.get("position_count"),
            "orders": recon.get("order_count"),
            "equity": round(float(account["equity"])) if "equity" in account else None,
            "news": {s.get("symbol"): s.get("state") for s in news.get("symbols", [])},
            "next_news": [f"{e.get('currency')} {e.get('name')}" for e in news.get("events", [])[:3]],
            "sentiment": sentiment.get("regime") if sentiment.get("ok") else "UNAVAILABLE",
            "ai_bridge_age_s": self.clock() - int(heartbeat["at_utc"]) if "at_utc" in heartbeat else None,
        }

    def status_text(self) -> str:
        d = self.status_data()
        ea = "STALE (EA không cập nhật)" if d["stale"] else f"cập nhật {d['snapshot_age_s']}s trước"
        news = ", ".join(f"{k}:{v}" for k, v in d["news"].items()) or "--"
        bridge = "--" if d["ai_bridge_age_s"] is None else (
            "ONLINE" if d["ai_bridge_age_s"] <= 120 else f"OFFLINE ({d['ai_bridge_age_s']}s)")
        return (f"EA: {d['runtime_state']} ({ea})\n"
                f"Vào lệnh (theo EA): {d['operator_mode']}\n"
                f"Phiên live: {d['session']}\n"
                f"Vị thế / lệnh chờ: {d['positions']} / {d['orders']}\n"
                f"Equity: {d['equity']}\n"
                f"News Guard: {news}\n"
                f"Tin sắp tới: {'; '.join(d['next_news']) or '--'}\n"
                f"Sentiment: {d['sentiment']}\n"
                f"AI Bridge: {bridge}")

    # -- notifications (N1) -------------------------------------------------
    def notify_audit(self):
        path = self.root / "logs" / "audit.jsonl"
        try:
            size = path.stat().st_size
        except OSError:
            return
        pos = int(self.state["audit_pos"])
        if self.state["audit_size"] == 0 and pos == 0:
            self.state["audit_pos"] = self.state["audit_size"] = size     # first run: start at the end
            return
        if size < pos:            # rotated (G15): the new file starts from zero
            pos = 0
        with path.open("rb") as fh:
            fh.seek(pos)
            chunk = fh.read(2_000_000)
        end = chunk.rfind(b"\n")
        if end < 0:
            self.state["audit_size"] = size
            return
        for raw in chunk[:end].splitlines():
            try:
                ev = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            self.audit_event(ev)
        self.state["audit_pos"] = pos + end + 1
        self.state["audit_size"] = size

    def audit_event(self, ev: dict):
        kind = ev.get("event_type", "")
        reasons = ev.get("reason_codes", []) or []
        notify = self.config["notify"]
        if kind in TRADE_EVENTS and notify.get("trades"):
            d = ev.get("details", {}) or {}
            setup = str(ev.get("entity_id", "")).split("-", 1)[0]
            result = ""
            if kind == "TRADE_EXITED" and "realized_known" in d:          # G20
                if d.get("realized_known") and d.get("realized_r") is not None:
                    result = f"\nKết quả: {d['realized_r']:+.2f}R ({d.get('realized_money', 0):+.2f})  thoát: {d.get('exit_cause', '')}"
                elif d.get("realized_known"):
                    result = f"\nKết quả: {d.get('realized_money', 0):+.2f} (không tính được R)  thoát: {d.get('exit_cause', '')}"
                else:
                    result = "\nKết quả: chưa thấy deal đóng trong lịch sử"
            self.broadcast(f"{TRADE_EVENTS[kind]} {ev.get('symbol', '')} {setup} {d.get('profile', '')}\n"
                           f"Trạng thái: {ev.get('state_after', '')}  lý do: {','.join(reasons)}\n"
                           f"MFE {d.get('mfe_r', 0)}R  MAE {d.get('mae_r', 0)}R  ({ev.get('occurred_at_utc', '')})" + result)
            return
        alert = kind in ALERT_EVENTS or any(any(k in r for k in ALERT_REASONS) for r in reasons)
        if alert and notify.get("alerts"):
            last = self.state["alerts_at"].get(kind, 0)
            if self.clock() - last < ALERT_THROTTLE:
                return
            self.state["alerts_at"][kind] = self.clock()
            self.broadcast(f"CẢNH BÁO {kind}: {','.join(reasons)} ({ev.get('occurred_at_utc', '')})")

    def notify_reports(self):
        if not self.config["notify"].get("ai_reports"):
            return
        for kind, title in REPORT_TYPES.items():
            rep = read_json(self.root / "ai" / "reports" / f"{kind}.json")
            if not isinstance(rep, dict) or rep.get("status") != "OK":
                continue
            rid = rep.get("request_id", "")
            if not rid or self.state["reports_seen"].get(kind) == rid:
                continue
            first = kind not in self.state["reports_seen"]
            self.state["reports_seen"][kind] = rid
            if first:                       # the report present at start-up is not news
                continue
            lines = [str(rep.get("summary", ""))] + [f"[{f.get('severity')}] {f.get('detail')}"
                                                     for f in rep.get("findings", [])[:6]]
            self.broadcast(f"{title} (AI):\n" + "\n".join(lines))

    def notify_news(self):
        if not self.config["notify"].get("news"):
            return
        news = read_json(self.root / "current" / "news_state.json") or {}
        t = self.clock()
        for e in news.get("events", []):
            at = int(e.get("time_utc", 0))
            key = f"{at}:{e.get('currency')}:{e.get('name')}"
            if 0 < at - t <= NEWS_LEAD and key not in self.state["news_seen"]:
                self.state["news_seen"].append(key)
                minutes = max(1, (at - t) // 60)
                self.broadcast(f"TIN HIGH sau {minutes} phút: {e.get('currency')} {e.get('name')} "
                               f"(dự báo {e.get('forecast') or '--'}, trước {e.get('previous') or '--'})")

    # -- loop ---------------------------------------------------------------
    def run_once(self, poll_timeout: int | None = None):
        timeout = self.config["poll_timeout"] if poll_timeout is None else poll_timeout
        try:
            body = self.api.call("getUpdates", {"offset": self.state["offset"], "timeout": timeout,
                                                "allowed_updates": ["message"]}, timeout=timeout + 10)
            for update in body.get("result", []):
                self.handle_update(update)
        except ConnectionError as exc:
            self.log("POLL_FAILED", detail=redact(exc, self.token)[:200])
        self.poll_results()
        self.poll_asks()
        self.notify_audit()
        self.notify_reports()
        self.notify_news()
        self.flush()
        self.save()


def load_config(path: str | None) -> dict:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        notify = user.pop("notify", {})
        config.update(user)
        config["notify"].update(notify)
    return config


def load_token(config: dict) -> str:
    token = os.environ.get("EEA_TELEGRAM_TOKEN", "").strip()
    if not token and config.get("token_file"):
        token = Path(config["token_file"]).read_text(encoding="utf-8").strip()
    return token


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue-root", required=True, help="MQL5/Files/EnterpriseEA folder of the terminal")
    parser.add_argument("--config", required=True, help="JSON config with operators/viewers (see telegram.example.json)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--loop", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    token = load_token(config)
    if not token:
        print("No bot token: set EEA_TELEGRAM_TOKEN or token_file", file=sys.stderr)
        return 2
    if not config["operators"]:
        print("No operator configured", file=sys.stderr)
        return 2
    gw = Gateway(Path(args.queue_root), config, TelegramApi(token), token)
    gw.log("GATEWAY_STARTED", version=VERSION, pid=os.getpid(), operators=len(gw.operators), viewers=len(gw.viewers))
    if args.once:
        gw.run_once(poll_timeout=0)
        return 0
    while True:
        try:
            gw.run_once()
        except Exception as exc:  # keep polling; the EA never depends on the gateway
            gw.log("GATEWAY_ERROR", detail=redact(exc, token)[:200])
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
