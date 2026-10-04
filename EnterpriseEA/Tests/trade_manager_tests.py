"""REQ-005 Trade Manager: lifecycle, SCALP/SWING profiles and protective actions."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


class TradeManagerProfileTests(unittest.TestCase):
    def setUp(self):
        self.tm = read("Runtime/TradeManagerRuntime.mqh")

    def test_scalp_and_swing_never_share_parameters(self):
        profile = section(self.tm, "void EEA_TradeProfileFor")
        swing, scalp = profile.split("return;", 1)
        self.assertIn("EEA_TM_TRAIL_STRUCTURE", swing)
        self.assertIn("p.timeout_bars=120", swing)
        self.assertIn("EEA_TM_TRAIL_ATR", scalp)
        self.assertIn("p.timeout_bars=36", scalp)
        self.assertIn("p.partial_at_r=1.0", scalp)
        self.assertIn("p.partial_at_r=1.5", swing)

    def test_lifecycle_and_metrics_follow_spec_section_6(self):
        observe = section(self.tm, "string EEA_TradeManagerObserveBars")
        for token in ('"PROVING"', '"WORKING"', '"MATURE"', "t.mfe_r", "t.mae_r",
                      "t.bar_05r", "t.bar_1r", "t.bar_2r", '"TRADE_UNDERPERFORMING"',
                      '"STRUCTURE_INVALIDATED"', '"TIME_STOP"'):
            self.assertIn(token, observe)
        # TC-012: underperforming is a flag, not an exit.
        flag = observe.split('"TRADE_UNDERPERFORMING"', 1)[0].rsplit("if(", 1)[1]
        self.assertNotIn("exit_reason", flag)

    def test_structure_invalidation_only_before_break_even(self):
        observe = section(self.tm, "string EEA_TradeManagerObserveBars")
        self.assertIn("if(!t.be_done && t.zone_low>0.0", observe)

    def test_revoked_session_only_moves_profitable_positions_to_break_even(self):
        update = section(self.tm, "void EEA_TradeManagerUpdate")
        revoked = update.split("if(!entries_permitted)", 1)[1].split("else if(t.exit_request", 1)[0]
        self.assertIn("now_r>0.0", revoked)
        self.assertIn('"SESSION_REVOKED_BREAK_EVEN"', revoked)
        self.assertNotIn("EEA_TradeManagerClose", revoked)
        self.assertNotIn("TRAIL", revoked)

    def test_stops_only_tighten_and_trail_stays_beyond_break_even(self):
        modify = section(self.tm, "bool EEA_TradeManagerModifyStop")
        self.assertIn('"TRADE_MANAGER_STOP_NOT_TIGHTER"', modify)
        self.assertIn('"TRADE_MANAGER_STOP_TOO_CLOSE"', modify)
        update = section(self.tm, "void EEA_TradeManagerUpdate")
        self.assertIn("t.direction*(trail-be_price)>0.0", update)

    def test_actions_are_authorized_idempotent_and_never_entry_recovery(self):
        modify = section(self.tm, "bool EEA_TradeManagerModifyStop")
        close = section(self.tm, "bool EEA_TradeManagerClose")
        for body in (modify, close):
            self.assertIn("EEA_TradeManagerAuthorization(t,", body)
            self.assertIn('"manage-"+t.intent.candidate_id', body)
        self.assertIn("EEA_ExecutionModifyProtective(", modify)
        self.assertIn("EEA_ExecutionClosePosition(", close)
        recovery = read("Storage/ExecutionRecoveryStore.mqh")
        self.assertIn('StringFind(idempotency_key,"manage-")!=0', recovery)
        self.assertIn('StringFind(idempotency_key,"-cancel-")<0', recovery)

    def test_pending_exit_is_retried_and_persisted(self):
        self.assertIn('EEA_PendingS("exit_request",t.exit_request)', self.tm)
        update = section(self.tm, "void EEA_TradeManagerUpdate")
        self.assertIn('else if(t.exit_request!="")', update)


class TradeManagerIntegrationTests(unittest.TestCase):
    def test_close_position_is_a_gated_reducing_action(self):
        gate = read("Runtime/ExecutionGate.mqh")
        self.assertIn('"CLOSE_POSITION_INVALID"', gate)
        self.assertIn("intent.action>EEA_EXEC_ACTION_CLOSE_POSITION", gate)
        adapter = read("Runtime/ExecutionAdapter.mqh")
        close = adapter.split("bool EEA_ExecutionClosePosition", 1)[1].split("\nbool ", 1)[0]
        self.assertIn("request.position = (ulong)intent.position_ticket;", close)
        self.assertIn("EEA_ExecutionGateCheck(", close)

    def test_entries_register_and_shell_updates_every_timer(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn("EEA_TradeManagerRegister(trades,observer.root,intent,result.request_ticket,", live)
        self.assertIn("EEA_TradeManagerHasCandidate(trades,candidate_id)", live)
        shell = read("EnterpriseEA.mq5")
        self.assertIn("EEA_TradeManagerLoad(g_trade_manager,g_config.data_root)", shell)
        self.assertIn("!g_pending_runtime.entry_permission_revoked);", shell)


if __name__ == "__main__":
    unittest.main()
