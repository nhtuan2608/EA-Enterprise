"""Command queue and manual trade actions (G8, TC-CQ-01..11)."""
import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


def validate_envelope(c, now, account, config, armed):
    """Mirror of EEA_CommandValidateEnvelope."""
    if c["source"] != "PANEL":
        return "COMMAND_SOURCE_NOT_ALLOWED"
    if c["action"] not in {"CLOSE", "PARTIAL", "BE", "TRAIL", "CANCEL", "CLOSE_ALL_EA"}:
        return "COMMAND_ACTION_INVALID"
    if c["expires_at_utc"] <= 0 or now > c["expires_at_utc"]:
        return "COMMAND_EXPIRED"
    if c["expires_at_utc"] - c["issued_at_utc"] > 60:
        return "COMMAND_TTL_INVALID"
    if c["account"] != account or c["config"] != config:
        return "COMMAND_IDENTITY_MISMATCH"
    if not armed:
        return "COMMAND_EA_NOT_ARMED"
    if c["action"] == "PARTIAL" and not 0.1 <= c["fraction"] <= 0.9:
        return "COMMAND_PARTIAL_INVALID"
    if c["action"] != "CLOSE_ALL_EA" and c["ticket"] <= 0:
        return "COMMAND_TICKET_INVALID"
    return ""


def partial_volume(volume, fraction, step, vmin):
    part = math.floor(volume * fraction / step + 1e-9) * step
    if part < vmin - 1e-12 or volume - part < vmin - 1e-12:
        return None
    return round(part, 8)


def cmd(**over):
    c = dict(source="PANEL", action="CLOSE", issued_at_utc=1000, expires_at_utc=1060, account="acc", config="cfg",
             fraction=0.0, ticket=123)
    c.update(over)
    return c


class CommandEnvelopeTests(unittest.TestCase):
    def test_valid_close(self):
        self.assertEqual(validate_envelope(cmd(), 1010, "acc", "cfg", True), "")

    def test_expired_and_ttl(self):  # TC-CQ-03
        self.assertEqual(validate_envelope(cmd(), 1061, "acc", "cfg", True), "COMMAND_EXPIRED")
        self.assertEqual(validate_envelope(cmd(expires_at_utc=1200), 1010, "acc", "cfg", True), "COMMAND_TTL_INVALID")

    def test_sources_and_actions(self):  # TC-CQ-11
        self.assertEqual(validate_envelope(cmd(source="AI"), 1010, "acc", "cfg", True), "COMMAND_SOURCE_NOT_ALLOWED")
        self.assertEqual(validate_envelope(cmd(source="TELEGRAM"), 1010, "acc", "cfg", True), "COMMAND_SOURCE_NOT_ALLOWED")
        self.assertEqual(validate_envelope(cmd(action="OPEN_BUY"), 1010, "acc", "cfg", True), "COMMAND_ACTION_INVALID")

    def test_locked_when_not_armed(self):  # TC-CQ-09 / C3
        self.assertEqual(validate_envelope(cmd(), 1010, "acc", "cfg", False), "COMMAND_EA_NOT_ARMED")

    def test_partial_volume(self):  # TC-CQ-05 / C4
        self.assertIsNone(partial_volume(0.01, 0.5, 0.01, 0.01))
        self.assertEqual(partial_volume(0.10, 0.5, 0.01, 0.01), 0.05)
        self.assertEqual(partial_volume(0.10, 0.75, 0.01, 0.01), 0.07)
        self.assertEqual(partial_volume(0.10, 0.25, 0.01, 0.01), 0.02)


class CommandQueueSourceTests(unittest.TestCase):
    def setUp(self):
        self.cq = read("Runtime/CommandQueue.mqh")

    def test_envelope_mirror_matches_source(self):
        env = section(self.cq, "string EEA_CommandValidateEnvelope")
        for token in ('c.source!="PANEL"', '"COMMAND_EXPIRED"', "EEA_CMD_TTL_SECONDS", '"COMMAND_EA_NOT_ARMED"',
                      "c.partial_fraction<0.1 || c.partial_fraction>0.9", '"COMMAND_IDENTITY_MISMATCH"'):
            self.assertIn(token, env)
        self.assertIn("#define EEA_CMD_TTL_SECONDS 60", self.cq)

    def test_once_only_and_state_checks(self):  # TC-CQ-02 / TC-CQ-04
        process = section(self.cq, "int EEA_CommandProcessQueue")
        self.assertIn('EEA_IdempotencyMarkerPath(root,"cmd-"+c.id)', process)
        self.assertIn('EEA_IdempotencyMarkerWrite(root,"cmd-"+c.id)', process)
        self.assertIn('"/done/"', process)
        action = section(self.cq, "string EEA_CommandPositionAction")
        self.assertIn('"COMMAND_STATE_CHANGED"', action)
        self.assertIn('"COMMAND_NOT_EA_POSITION"', action)                 # C1 / TC-CQ-08
        self.assertIn('"COMMAND_PARTIAL_BELOW_MIN_VOLUME"', action)

    def test_actions_reuse_the_guarded_paths(self):
        action = section(self.cq, "string EEA_CommandPositionAction")
        self.assertIn("EEA_TradeManagerClose(", action)
        self.assertIn("EEA_TradeManagerModifyStop(", action)
        self.assertIn("t.partial_done=true", action)
        self.assertIn("t.be_done=true", action)
        self.assertIn("t.trail_active=true", action)
        self.assertNotIn("OrderSend", self.cq)
        cancel = section(self.cq, "string EEA_CommandCancelOrder")
        self.assertIn("EEA_PendingRequestCancel(", cancel)

    def test_close_all_covers_positions_and_orders(self):  # TC-CQ-10
        execute = section(self.cq, "string EEA_CommandExecute")
        self.assertIn('EEA_CommandPositionAction("CLOSE"', execute)
        self.assertIn("EEA_CommandCancelOrder(", execute)
        self.assertIn('"COMMAND_PARTIAL_FAILURE"', execute)

    def test_manual_trail_starts_trade_manager_trailing(self):  # C6
        tm = read("Runtime/TradeManagerRuntime.mqh")
        self.assertIn("else if(t.trail_active || t.mfe_r>=p.trail_start_r)", tm)

    def test_panel_confirmation_flow(self):  # C2 / C5
        panel = read("Runtime/SymbolSelectionPanel.mqh")
        self.assertIn("GetTickCount()-g_panel_state.trade_confirm_tick<15000", panel)
        click = section(panel, "void EEA_SymbolPanelHandleTradeClick")
        self.assertIn("g_panel_state.trade_closeall_stage==2", click)
        self.assertIn('g_panel_state.cmd_request_action="CLOSE_ALL_EA"', click)

    def test_schema_whitelist(self):
        schema = json.loads(read("schemas/ea-command.schema.json"))
        self.assertEqual(schema["properties"]["source"]["enum"], ["PANEL"])
        self.assertNotIn("OPEN", " ".join(schema["properties"]["action"]["enum"]))


class PanelRequestNullSafetyTests(unittest.TestCase):
    def test_requests_are_initialised_and_checked_by_length(self):
        panel = read("Runtime/SymbolSelectionPanel.mqh")
        init = section(panel, "bool EEA_SymbolPanelInit")
        for field in ("session_request", "recovery_request", "ai_request", "cmd_request_action"):
            self.assertIn("g_panel_state." + field + '=""', init)
        shell = read("EnterpriseEA.mq5")
        self.assertIn("StringLen(g_panel_state.cmd_request_action)>0", shell)
        self.assertNotIn('g_panel_state.cmd_request_action!=""', shell)
        self.assertNotIn('   if(request=="") return;', shell)


if __name__ == "__main__":
    unittest.main()
