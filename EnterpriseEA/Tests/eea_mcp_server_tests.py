"""MCP server (bridge/eea_mcp_server.py): JSON-RPC protocol, read-only tools, control tools and the EA's MCP source."""
import io
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

import eea_mcp_server as ms  # noqa: E402

NOW = 1_800_000_000
STATUS = {"document_version": "bots-status-v1.0.0", "account_id": "fnv1a32:abc", "config_version": "observer-v1.0.0",
          "state_loaded": True, "mcp_commands": True, "symbol": "XAUUSD", "written_at_utc": NOW - 3,
          "bots": [{"code": "S07", "active": True, "mode": "LIVE"}]}


def mql_field(json_text, name):
    """Python copy of EEA_RiskLedgerField (Storage/RiskLedgerStore.mqh): "key": then a quoted string or up to , or }."""
    key = '"' + name + '":'
    at = json_text.find(key)
    if at < 0:
        return ""
    start = at + len(key)
    if start < len(json_text) and json_text[start] == '"':
        end = json_text.find('"', start + 1)
        return "" if end < 0 else json_text[start + 1:end]
    end = json_text.find(",", start)
    if end < 0:
        end = json_text.find("}", start)
    return "" if end < 0 else json_text[start:end]


class Case(unittest.TestCase):
    control = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "EnterpriseEA"
        (self.root / "current").mkdir(parents=True)
        self.t = NOW
        self.srv = ms.EeaMcp(self.root, allow_control=self.control, clock=lambda: self.t, operator="tester")
        self.srv.RESULT_WAIT = 0.0
        self.srv.sleep = lambda s: None

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, payload):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def call(self, name, args=None, mid=7):
        r = self.srv.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                             "params": {"name": name, "arguments": args or {}}})
        self.assertEqual(r["id"], mid)
        res = r["result"]
        text = res["content"][0]["text"]
        return res["isError"], (json.loads(text) if text.startswith("{") else text)


class ProtocolTests(Case):
    def test_initialize_list_and_notifications(self):
        r = self.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-03-26", "capabilities": {}}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", r["result"]["capabilities"])
        r = self.srv.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "1999"}})
        self.assertEqual(r["result"]["protocolVersion"], ms.PROTOCOLS[0])
        self.assertIsNone(self.srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = [t["name"] for t in self.srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]]
        self.assertEqual(sorted(names), sorted(["health_check", "bots_status", "account_status", "read_bot_log",
                                                "read_audit", "vhedge_groups"]))
        self.assertEqual(self.srv.handle({"jsonrpc": "2.0", "id": 4, "method": "nope"})["error"]["code"], -32601)
        self.assertEqual(self.srv.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                          "params": {"name": "bot_off"}})["error"]["code"], -32602)

    def test_stdio_loop(self):
        lines = [{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "method": "notifications/initialized"}]
        stdin = io.BytesIO(("\n".join(json.dumps(m) for m in lines) + "\nnot json\n").encode())
        stdout = io.BytesIO()
        ms.serve(self.srv, stdin, stdout)
        out = [json.loads(x) for x in stdout.getvalue().decode().splitlines()]
        self.assertEqual(out[0], {"jsonrpc": "2.0", "id": 1, "result": {}})
        self.assertEqual(out[1]["error"]["code"], -32700)
        self.assertEqual(len(out), 2)


class ReadToolTests(Case):
    def test_bots_status_and_staleness(self):
        err, text = self.call("bots_status")
        self.assertTrue(err)
        self.assertIn("bots_status.json", text)
        self.write("current/bots_status.json", STATUS)
        err, data = self.call("bots_status")
        self.assertFalse(err)
        self.assertEqual((data["age_seconds"], data["stale"]), (3, False))
        self.t += 500
        self.assertTrue(self.call("bots_status")[1]["stale"])

    def test_bot_log_summary_and_filters(self):
        g = time.gmtime(NOW)
        rel = f"logs/bots-{g.tm_year:04d}{g.tm_mon:02d}.jsonl"
        rows = [{"at_utc": NOW - 60, "server": "x", "bot": "XRT", "event": "DECISION", "mode": "LIVE", "text": "plan", "data": {}},
                {"at_utc": NOW - 50, "server": "x", "bot": "XRT", "event": "NEAR", "mode": "LIVE", "text": "near", "data": {"score": 0.4}},
                {"at_utc": NOW - 40, "server": "x", "bot": "CTXLIMIT", "event": "EXIT", "mode": "SHADOW", "text": "tp", "data": {"r": 2.0}}]
        self.write(rel, "\n".join(json.dumps(r) for r in rows) + "\n")
        err, data = self.call("read_bot_log")
        self.assertFalse(err)
        self.assertEqual([x["event"] for x in data["lines"]], ["DECISION", "EXIT"])        # NEAR left out
        self.assertEqual(data["summary"]["bots"]["CTXLIMIT"]["shadow_r"], 2.0)
        self.assertEqual(len(self.call("read_bot_log", {"include_near": True})[1]["lines"]), 3)
        self.assertEqual(self.call("read_bot_log", {"bot": "xrt", "events": ["NEAR"]})[1]["lines"][0]["text"], "near")
        self.assertNotIn("lines", self.call("read_bot_log", {"summary_only": True})[1])
        self.assertTrue(self.call("read_bot_log", {"bot": "FOO"})[0])

    def test_audit_filters_runtime_and_age(self):
        ev = lambda t, et: json.dumps({"occurred_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t)),
                                       "event_type": et, "reason_codes": ["R"]})
        self.write("logs/audit.jsonl", "\n".join([ev(NOW - 90000, "BOT_ENABLED"), ev(NOW - 100, "RUNTIME_REFRESHED"),
                                                  ev(NOW - 50, "BOT_DISABLED"), ev(NOW - 10, "TRADE_ENTERED")]) + "\n")
        data = self.call("read_audit")[1]
        self.assertEqual([e["event_type"] for e in data["events"]], ["BOT_DISABLED", "TRADE_ENTERED"])
        self.assertEqual(self.call("read_audit", {"event_type": "bot"})[1]["count"], 1)
        self.assertEqual(self.call("read_audit", {"include_runtime": True})[1]["count"], 3)

    def test_vhedge_groups(self):
        head = "vhedge-groups-v1|5|XAUUSD|116119"
        legs = "|1|1|4100.0|4090.0|0.10|1.0|111|0.0|1|-1|4099.8|4109.8|0.10|1.0|112|0.0|0|0|0|0|0|1|0|0"
        g = f"G|4|0|{NOW - 900}|{NOW - 600}|{NOW - 600}|0|1|0|6.6|19.8|0|0|0|0|0|0|0|0|1|" + legs
        self.write("current/bots/vhedge_groups.txt", head + "\n" + g + "\n")
        (self.root.parent / "VHedge_XAUUSD_116119.csv").write_text(
            "mode;profile;group;v_time;signal_time;open_time;close_time;side;U;atr;buy_entry;sell_entry;buy_sl;sell_sl;"
            "add_entry;tp;result_price;result_U;note\nSHADOW;G119;3;a;b;c;d;BUY;19.8;6.6;1;2;3;4;5;6;7;2.5;tp\n", encoding="utf-8")
        data = self.call("vhedge_groups")[1]
        self.assertEqual(data["open_groups"][0]["id"], 4)
        self.assertEqual([l["leg"] for l in data["open_groups"][0]["open_legs"]], ["BUY", "SELL"])
        self.assertEqual(data["closed_recent_sum_U"], 2.5)

    def test_health_check(self):
        data = self.call("health_check")[1]
        self.assertFalse(data["ok"])
        self.assertIn("current/bots_status.json: MISSING", data["problems"])
        self.write("current/bots_status.json", STATUS)
        self.write("current/live_session.json", {"status": "ACTIVE", "valid_until_utc": NOW + 3600})
        self.write("current/execution_controller_state.json", {"kill_active": True})
        self.write("current/remote/bot_commands/old.json", "{}")
        import os
        os.utime(self.root / "current/remote/bot_commands/old.json", (NOW - 100, NOW - 100))
        problems = self.call("health_check")[1]["problems"]
        self.assertIn("kill switch đang BẬT", problems)
        self.assertIn("live session hết hạn trong < 24 giờ", problems)
        self.assertTrue(any("chưa được EA xử lý" in p for p in problems))


class ControlToolTests(Case):
    control = True

    def commands(self):
        d = self.root / "current" / "remote" / "bot_commands"
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]

    def test_control_tools_only_with_the_flag(self):
        names = [t["name"] for t in self.srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]]
        for n in ("bot_off", "bot_on", "bot_confirm", "all_bots_off"):
            self.assertIn(n, names)

    def test_off_writes_an_mcp_command_without_telegram_claims(self):
        self.write("current/bots_status.json", STATUS)
        err, data = self.call("bot_off", {"bot": "vhedge", "reason": "test"})
        self.assertFalse(err)
        self.assertEqual(data["status"], "PENDING")
        cmd = self.commands()[0]
        self.assertEqual((cmd["source"], cmd["action"], cmd["bot"], cmd["role"]), ("MCP", "BOT_DISABLE", "VHEDGE", "OPERATOR"))
        self.assertEqual((cmd["account_id"], cmd["config_version"], cmd["user_id"]), ("fnv1a32:abc", "observer-v1.0.0", "tester"))
        self.assertEqual(cmd["mcp_sequence"], NOW * 1000)
        for k in ("private_chat_attested", "sender_authenticated", "source_authenticated", "gateway_sequence", "reason"):
            self.assertNotIn(k, cmd)
        raw = next((self.root / "current" / "remote" / "bot_commands").glob("*.json")).read_text(encoding="utf-8")
        for key in ("source", "action", "bot", "role", "account_id", "config_version", "mcp_sequence", "issued_at_utc"):
            self.assertEqual(mql_field(raw, key), str(cmd[key]), key)       # what the EA reader sees
        self.assertEqual(cmd["expires_at_utc"] - cmd["issued_at_utc"], self.srv.COMMAND_TTL)
        log = json.loads((self.root / "logs" / "mcp.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((log["operator"], log["reason"], log["status"]), ("tester", "test", "PENDING"))

    def test_sequences_rise_and_all_off(self):
        self.write("current/bots_status.json", STATUS)
        self.call("all_bots_off")
        seqs = [c["mcp_sequence"] for c in self.commands()]
        self.assertEqual(len(seqs), 4)
        self.assertEqual(seqs, sorted(set(seqs)))
        self.assertEqual(sorted(c["bot"] for c in self.commands()), sorted(ms.BOT_CODES))

    def test_on_returns_the_code_only_when_the_ea_holds_it(self):
        self.write("current/bots_status.json", STATUS)
        orig = self.srv.wait_result
        self.srv.wait_result = lambda cid: {"status": "APPLIED", "applied": True,
                                            "reason_codes": ["BOT_ENABLE_CONFIRMATION_PENDING"]}
        data = self.call("bot_on", {"bot": "XRT"})[1]
        cmd = self.commands()[0]
        self.assertEqual(cmd["action"], "BOT_REQUEST_ENABLE")
        self.assertRegex(cmd["confirmation_nonce"], r"^\d{6}$")
        self.assertEqual(data["code"], cmd["confirmation_nonce"])
        self.assertLessEqual(cmd["nonce_expires_at_utc"] - cmd["issued_at_utc"], 120)
        self.assertIn("bot_confirm", data["next"])
        self.assertNotIn(cmd["confirmation_nonce"], (self.root / "logs" / "mcp.jsonl").read_text(encoding="utf-8"))
        self.srv.wait_result = orig
        err, _ = self.call("bot_confirm", {"bot": "XRT", "code": "12"})
        self.assertTrue(err)
        self.call("bot_confirm", {"bot": "XRT", "code": data["code"]})
        self.assertEqual(self.commands()[-1]["action"], "BOT_CONFIRM_ENABLE")

    def test_refuses_without_a_live_ea(self):
        self.assertTrue(self.call("bot_off", {"bot": "S07"})[0])                 # no status file
        self.write("current/bots_status.json", {**STATUS, "written_at_utc": NOW - 1000})
        self.assertIn("cũ", self.call("bot_off", {"bot": "S07"})[1])
        self.write("current/bots_status.json", {**STATUS, "mcp_commands": False})
        self.assertIn("InpBotsMcpCommands", self.call("bot_off", {"bot": "S07"})[1])
        self.assertEqual(self.commands(), [])

    def test_result_is_returned(self):
        self.write("current/bots_status.json", STATUS)
        orig_write = self.srv.write_bot_command

        def write_and_answer(*a, **k):
            cid = orig_write(*a, **k)
            self.write(f"current/remote/results/{cid}.json", {"command_id": cid, "status": "APPLIED", "applied": True,
                                                              "state_before": "ACTIVE", "state_after": "INACTIVE",
                                                              "reason_codes": ["BOT_DISABLED_MCP"]})
            return cid
        self.srv.write_bot_command = write_and_answer
        data = self.call("bot_off", {"bot": "CTXLIMIT"})[1]
        self.assertEqual((data["status"], data["state_after"]), ("APPLIED", "INACTIVE"))


class EaMcpSourceTests(unittest.TestCase):
    def setUp(self):
        self.host = (ROOT / "Bots/BotHost.mqh").read_text(encoding="utf-8-sig")
        self.state = (ROOT / "Bots/BotState.mqh").read_text(encoding="utf-8-sig")

    def test_own_sequence_and_no_telegram_claims(self):
        self.assertIn('sequence=StringToInteger(EEA_RiskLedgerField(json,mcp ? "mcp_sequence" : "gateway_sequence"));', self.host)
        self.assertIn("(mcp ? claims : !attested)", self.host)
        self.assertIn("sequence<=(mcp ? s.last_mcp_sequence : s.last_gateway_sequence)", self.host)
        self.assertIn('if(mcp && !g_bots_allow_mcp) return "BOT_COMMAND_SOURCE_DISABLED";', self.host)
        self.assertIn("if(mcp) g_bots_state.last_mcp_sequence=sequence; else g_bots_state.last_gateway_sequence=sequence;", self.host)
        self.assertIn("EEA_BotsSetActive(g_bots_state,bot,on,root,source,command_id,audit,reason)", self.host)
        self.assertIn('\\"last_mcp_sequence\\":', self.state)
        self.assertIn('s.last_mcp_sequence=StringToInteger(EEA_RiskLedgerField(json,"last_mcp_sequence"));', self.state)
        self.assertRegex((ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8-sig"),
                         r"input bool\s+InpBotsMcpCommands\s+= true;")


if __name__ == "__main__":
    unittest.main()
