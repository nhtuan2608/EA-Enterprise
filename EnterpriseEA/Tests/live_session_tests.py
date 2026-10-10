"""Session authorization: one signed, time-boxed permission replaces per-trade documents."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


class LiveSessionGateTests(unittest.TestCase):
    def setUp(self):
        self.module = read("Runtime/LiveSessionAuthorization.mqh")

    def test_session_is_time_boxed_to_seven_days_and_scoped(self):
        active = section(self.module, "bool EEA_LiveSessionActive")
        self.assertIn("#define EEA_LIVE_SESSION_MAX_SECONDS (7*86400)", self.module)
        for token in ('"LIVE_SESSION_REVOKED"', '"LIVE_SESSION_EXPIRED"', '"LIVE_SESSION_NOT_STARTED"',
                      '"LIVE_SESSION_WINDOW_INVALID"', '"LIVE_SESSION_SCOPE_INVALID"',
                      '"LIVE_SESSION_LIMITS_INVALID"', '"LIVE_SESSION_SYMBOLS_EMPTY"'):
            self.assertIn(token, active)

    def test_authorization_is_bound_and_limited_per_candidate(self):
        authorize = section(self.module, "bool EEA_LiveSessionAuthorize")
        for token in ('"LIVE_SESSION_IDENTITY_MISMATCH"', '"LIVE_SESSION_POLICY_CHANGED"',
                      '"LIVE_SESSION_ACCOUNT_TYPE_CHANGED"', '"LIVE_SESSION_SYMBOL_NOT_ALLOWED"',
                      '"LIVE_SESSION_DAILY_SWING_ENTRIES_REACHED"', '"LIVE_SESSION_DAILY_SCALP_ENTRIES_REACHED"',
                      '"LIVE_SESSION_DAILY_LOSS_REACHED"',
                      '"LIVE_SESSION_USAGE_PERSISTENCE_FAILED"'):
            self.assertIn(token, authorize)
        # The adapter still binds one authorization to exactly one intent.
        self.assertIn('d.intent_id=s.session_id+"-"+candidate_id;', authorize)
        self.assertIn("d.candidate_id=candidate_id;", authorize)
        self.assertIn('d.status="AUTHORIZED_CONTROLLED_LIVE";', authorize)

    def test_usage_is_durable_and_failure_blocks_entries(self):
        record = section(self.module, "bool EEA_LiveSessionRecordEntry")
        self.assertIn("EEA_LiveSessionUsageWrite(root,r.usage)", record)
        self.assertIn("r.usage_failed=true", record)
        # Re-signing a session must not reset the daily entry cap.
        today = section(self.module, "int EEA_LiveSessionEntriesToday")
        self.assertNotIn("session_id", today)
        self.assertNotIn("r.usage.session_id!=", record)

    def test_cancel_is_owned_by_the_placing_session(self):
        cancel = section(self.module, "bool EEA_LiveSessionCancelAuthorization")
        self.assertIn('StringFind(intent_id,s.session_id+"-")!=0', cancel)
        self.assertIn('"LIVE_SESSION_CANCEL_NOT_OWNED"', cancel)
        self.assertIn('"LIVE_SESSION_IDENTITY_MISMATCH"', cancel)


class LiveSessionIntegrationTests(unittest.TestCase):
    def test_live_loop_uses_session_and_keeps_document_fallback(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        on_timer = live.split("bool EEA_ControlledLiveOnTimer", 1)[1]
        self.assertIn("EEA_LiveSessionRuntime &session", on_timer)
        self.assertIn("EEA_LiveSessionAuthorize(session,", on_timer)
        self.assertIn("EEA_LiveAuthorizationStoreLoad(authorization_path,", on_timer)
        self.assertIn('"LIVE_AUTHORIZATION_CANDIDATE_MISMATCH"', on_timer)
        self.assertIn("EEA_ControlledLiveApplySessionCap(session_mode,session,ledger,plan,reason)", on_timer)
        self.assertIn("EEA_LiveSessionRecordEntry(session,observer.root,day_reset,entry_profile)", on_timer)
        self.assertIn('entry_profile=(strategy.zone_mode ? EEA_RiskProfileOf(strategy.profile[i]) : "SCALP")', on_timer)
        self.assertIn('params.idempotency_key="entry-"+candidate_id;', on_timer)
        cap = section(live, "bool EEA_ControlledLiveApplySessionCap")
        self.assertIn("MathMin(plan.base_risk_fraction,cap)", cap)

    def test_revoked_session_cancels_pending_orders(self):
        pending = read("Runtime/PendingOrderRuntime.mqh")
        self.assertIn("!entry_permission_revoked", pending)
        self.assertIn("EEA_LiveSessionCancelAuthorization(t.authorization_path", pending)
        shell = read("EnterpriseEA.mq5")
        self.assertIn("g_pending_runtime.entry_permission_revoked=g_live_session.present", shell)

    def test_sign_rechecks_state_and_guards_real_accounts(self):
        shell = read("EnterpriseEA.mq5")
        sign = section(shell, "bool EEA_LiveSessionSign")
        for token in ('"SESSION_RUNTIME_NOT_OBSERVING"', '"SESSION_REAL_ACCOUNT_NOT_ALLOWED"',
                      "EXECUTION_UNKNOWN_RECOVERY_REQUIRED", "g_pending_runtime.entries_blocked",
                      "EEA_ControlledLiveResolvePolicy", "EEA_RiskLimitsForPolicy",
                      '"LIVE_INITIAL_CAPITAL_UNKNOWN"', '"SESSION_NO_RESOLVED_SYMBOLS"',
                      "limits.per_trade_fraction", "limits.internal_daily_fraction",
                      "EEA_LiveSessionWriteController(false,", '"LIVE_SESSION_SIGNED"'):
            self.assertIn(token, sign)
        self.assertIn("input bool   InpSessionAllowRealAccount = false;", shell)
        revoke = section(shell, "bool EEA_LiveSessionRevoke")
        self.assertIn("EEA_LiveSessionWriteController(true,", revoke)
        self.assertIn('session.status="REVOKED"', revoke)

    def test_panel_requires_two_clicks_to_sign_and_one_to_revoke(self):
        panel = read("Runtime/SymbolSelectionPanel.mqh")
        self.assertIn("GetTickCount()-g_panel_state.session_confirm_tick<60000", panel)
        # Accept signs only a duration chosen first (one click to choose, one to accept).
        accept = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_SessionAccept"', 1)[1].split("Btn_SessionRevoke", 1)[0]
        self.assertIn('if(chosen!="") { g_panel_state.session_request=chosen;', accept)
        self.assertIn('"Choose 24h or 7 days first"', accept)
        handler = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Session24h" ||', 1)[1].split("Btn_Apply", 1)[0]
        self.assertIn("if(EEA_SymbolPanelSessionConfirming(action))", handler)
        self.assertIn('g_panel_state.session_request="REVOKE"', handler)
        # The panel never writes session files itself.
        self.assertNotIn("EEA_LiveSessionWrite", panel)


class InternalLossLimitTests(unittest.TestCase):
    def test_daily_and_weekly_internal_limits_cap_the_plan(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        room = section(live, "bool EEA_ControlledLiveInternalLossRoom")
        for token in ('"INTERNAL_DAILY_LOSS_LIMIT_REACHED"', '"INTERNAL_WEEKLY_BASIS_UNKNOWN"',
                      '"INTERNAL_WEEKLY_LOSS_LIMIT_REACHED"', "limits.internal_daily_fraction",
                      "limits.internal_weekly_fraction", "EEA_BalanceAtUtc(observer.reconciliation"):
            self.assertIn(token, room)
        plan = section(live, "bool EEA_ControlledLiveResolveV1Plan")
        self.assertIn("EEA_ControlledLiveInternalLossRoom(observer,ledger,policy.committed_policy,limits,loss_room,reason)", plan)
        self.assertIn("MathMin(limits.per_trade_fraction*weight*ledger.initial_capital,loss_room)", plan)   # G44 weight <= 1

    def test_open_stop_risk_is_subtracted_in_both_rooms_and_add_path_shares_it(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        room = section(live, "bool EEA_ControlledLiveInternalLossRoom")
        self.assertIn("EEA_ControlledLiveExistingStress(observer,open_stress,open_floating,reason)", room)
        self.assertIn("-daily_loss-open_stress;", room)
        self.assertIn("-(week_balance-equity)-open_stress;", room)
        self.assertLess(room.index("EEA_ControlledLiveExistingStress"), room.index("daily_room<=0.0"))
        pyramid = read("Integration/S06BPyramidRuntime.mqh")
        self.assertIn("EEA_ControlledLiveInternalLossRoom(observer,ledger,policy.committed_policy,limits,loss_room,reason)", pyramid)

    def test_prague_week_starts_on_monday(self):
        # Mirror of EEA_PragueWeekResetUtc's weekday arithmetic (1970-01-01 was a Thursday).
        def weekday(day_index):
            return (day_index + 4) % 7
        monday = 1791158400 // 86400  # 2026-10-05
        self.assertEqual(weekday(monday), 1)
        self.assertEqual((weekday(monday) + 6) % 7, 0)
        self.assertEqual((weekday(monday + 6) + 6) % 7, 6)


class LiveSessionProfileCapTests(unittest.TestCase):
    def test_scalp_and_swing_have_separate_daily_caps(self):
        module = read("Runtime/LiveSessionAuthorization.mqh")
        today = section(module, "int EEA_LiveSessionEntriesToday")
        self.assertIn('profile=="SWING" ? r.usage.swing_entries : r.usage.scalp_entries', today)
        record = section(module, "bool EEA_LiveSessionRecordEntry")
        self.assertIn('if(profile=="SWING") r.usage.swing_entries++; else r.usage.scalp_entries++;', record)
        load = section(module, "bool EEA_LiveSessionLoadPath")
        self.assertIn('"max_entries_per_day"', load)   # sessions signed before the split stay valid
        shell = read("EnterpriseEA.mq5")
        self.assertIn("input int    InpSessionMaxScalpPerDay   = 6;", shell)
        self.assertIn("input int    InpSessionMaxSwingPerDay   = 2;", shell)


if __name__ == "__main__":
    unittest.main()
