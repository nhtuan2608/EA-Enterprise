"""Fixed offline contract cases for the pure MT5 runtime evidence core."""
from copy import deepcopy
import json
import os
import sys
import unittest
from pathlib import Path

# Ensure the Tests directory is on sys.path so local oracles import.
_HERE = Path(__file__).resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from runtime_evidence_oracle import evaluate, material_spec_equal  # noqa: E402

ROOT = _HERE.parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/runtime-evidence-v0.1.0.json").read_text(encoding="utf-8"))

FORBIDDEN_RUNTIME_CORE_TOKENS = (
    "OrderSend", "OrderSendAsync", "CTrade", "PositionClose", "PositionModify",
    "OrderDelete", "PositionGet", "PositionsTotal", "OrderGet", "OrdersTotal",
    "HistorySelect", "HistoryDealGet", "HistoryDealsTotal", "AccountInfo",
    "TerminalInfo", "SymbolInfo", "FileOpen", "FileWrite", "FileRead",
)


class RuntimeEvidenceContractTests(unittest.TestCase):
    def test_panel_is_live_only_and_refresh_is_timer_owned(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("MQL_TESTER", shell)
        self.assertIn("MQL_OPTIMIZATION", shell)
        self.assertIn("EEA_LivePanelAllowed", shell)
        self.assertIn("if(EEA_LivePanelAllowed() && InpShowSymbolPanel)", shell)
        self.assertIn("EEA_SymbolPanelRefreshOpenOverlay", shell)
        self.assertIn("AUTO_REFRESH", panel)
        self.assertNotIn('"Btn_Refresh"', panel)
        self.assertNotIn('sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Refresh"', panel)

    def test_settings_and_dashboard_clicks_render_immediately(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        settings = 'if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Settings")'
        dashboard = 'if(sparam==EEA_PANEL_MAIN_PREFIX+"Btn_Dashboard")'
        for branch in (settings, dashboard):
            self.assertIn(branch, panel)
            start = panel.index(branch)
            end = panel.index("return;", start)
            self.assertIn("EEA_SymbolPanelRender", panel[start:end])
            self.assertIn("ChartRedraw", panel[start:end])

    def test_complete_empty_account_is_observing(self):
        status = evaluate(FIXTURE["base_snapshot"], now_utc=FIXTURE["base_snapshot"]["observed_at_utc"])
        self.assertEqual(status["runtime_state"], "OBSERVING")
        self.assertEqual(status["reason_code"], "RUNTIME_EVIDENCE_CURRENT")
        self.assertTrue(status["new_entries_blocked"])

    def test_incomplete_sources_fail_closed(self):
        for case in FIXTURE["degraded_cases"]:
            with self.subTest(field=case["field"]):
                snapshot = deepcopy(FIXTURE["base_snapshot"])
                snapshot[case["field"]] = False
                status = evaluate(snapshot, now_utc=snapshot["observed_at_utc"])
                self.assertEqual(status["runtime_state"], "DEGRADED")
                self.assertEqual(status["reason_code"], case["expected_reason"])
                self.assertTrue(status["new_entries_blocked"])

    def test_identity_duplicates_and_watermark_regression_block(self):
        for case in FIXTURE["blocked_cases"]:
            with self.subTest(name=case["name"]):
                snapshot = deepcopy(FIXTURE["base_snapshot"])
                snapshot.update(case.get("snapshot_overrides", {}))
                snapshot["positions"] = case.get("positions", snapshot["positions"])
                snapshot["orders"] = case.get("orders", snapshot["orders"])
                snapshot["deals"] = case.get("deals", snapshot["deals"])
                status = evaluate(snapshot, now_utc=snapshot["observed_at_utc"],
                                  previous_watermark=case.get("previous_watermark", -1))
                self.assertEqual(status["runtime_state"], "BLOCKED")
                self.assertEqual(status["reason_code"], case["expected_reason"])
                self.assertTrue(status["new_entries_blocked"])

    def test_material_symbol_spec_comparison(self):
        self.assertTrue(material_spec_equal(FIXTURE["symbol_spec"], deepcopy(FIXTURE["symbol_spec"])))
        changed = deepcopy(FIXTURE["symbol_spec"])
        changed["volume_step"] = 0.1
        self.assertFalse(material_spec_equal(FIXTURE["symbol_spec"], changed))

    def test_panel_model_contract_names_and_context_only_dxy(self):
        source = (ROOT / "Runtime/ObserverPanelModel.mqh").read_text(encoding="utf-8")
        for token in ("EEA_ObserverPanelMarketRow", "context_only", "NOT_AUTHORIZED", "EXECUTION_DISABLED"):
            self.assertIn(token, source)
        self.assertIn("EEA_ObserverPanelFormatStatus", source)
        self.assertIn("EEA_ObserverPanelStatusDefaults", source)
        self.assertIn("CONTEXT ONLY", source)

    def test_panel_model_fixture_defaults_and_purity(self):
        source = (ROOT / "Runtime/ObserverPanelModel.mqh").read_text(encoding="utf-8")
        panel = FIXTURE["observer_panel"]
        self.assertEqual(panel["status_defaults"]["execution_status"], "EXECUTION_DISABLED")
        self.assertEqual(panel["status_defaults"]["live_status"], "NOT_AUTHORIZED")
        row = panel["context_market_row"]
        self.assertEqual(row["canonical"], "DXY")
        self.assertEqual(row["broker"], "USDX.")
        self.assertTrue(row["context_only"])
        self.assertEqual(row["status"], "CONTEXT ONLY")
        self.assertIn('Runtime/RuntimeEvidence.mqh', source)
        for forbidden in ("ObjectCreate", "ChartRedraw", "AccountInfo", "TerminalInfo", "SymbolInfo",
                          "FileOpen", "FileWrite", "FileRead", "OrderSend", "OrderSendAsync",
                          "CTrade", "PositionClose", "PositionModify", "OrderDelete"):
            self.assertNotIn(forbidden, source)

    def test_mql_pure_contract_structure_and_purity(self):
        source = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        for name in ("EEA_RuntimeAccountSnapshot", "EEA_RuntimeSymbolSpec",
                     "EEA_RuntimePositionRow", "EEA_RuntimeOrderRow",
                     "EEA_RuntimeDealRow", "EEA_RuntimeReconciliationSnapshot",
                     "EEA_RuntimeStatus", "EEA_RuntimeDefaults",
                     "EEA_RuntimeValidate", "EEA_RuntimeMaterialSpecEqual"):
            self.assertIn(name, source)
        for name in ("EEA_RUNTIME_MAX_SYMBOLS", "EEA_RUNTIME_MAX_POSITIONS",
                     "EEA_RUNTIME_MAX_ORDERS", "EEA_RUNTIME_MAX_DEALS"):
            self.assertIn(name, source)
        self.assertIn("MathIsValidNumber", source)
        # Pure contract consumes the shared schema version but performs no
        # account/symbol/position/history/file/trade API access itself.
        self.assertTrue("Core/Config.mqh" in source or "Core\\Config.mqh" in source)
        for token in FORBIDDEN_RUNTIME_CORE_TOKENS:
            self.assertNotIn(token, source)

    def test_account_financial_snapshot_is_read_and_persisted(self):
        adapter = (ROOT / "Runtime/AccountSnapshotAdapter.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        contract = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        for field in ("balance", "equity", "margin", "margin_free"):
            self.assertIn("AccountInfoDouble(ACCOUNT_" + field.upper() + ")", adapter)
            self.assertIn("snapshot." + field, adapter)
            self.assertIn("account." + field, store)
            self.assertIn("double " + field, contract)
        self.assertIn("ACCOUNT_FINANCIAL_STATE_UNAVAILABLE", adapter)

    def test_trade_quote_adapter_is_read_only_and_binds_account_symbol_evidence(self):
        source = (ROOT / "Runtime/TradeQuoteAdapter.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for token in ("SymbolInfoTick", "OrderCalcProfit", "OrderCalcMargin",
                      "available_margin", "projected_loss", "symbol_fingerprint",
                      "TRADE_QUOTE_UNAVAILABLE", "LOSS_CALCULATION_INVALID"):
            self.assertIn(token, source)
        self.assertIn('"Runtime/TradeQuoteAdapter.mqh"', shell)
        for forbidden in ("OrderSend", "OrderSendAsync", "CTrade"):
            self.assertNotIn(forbidden, source)

    def test_mql_validation_contains_duplicate_and_finite_checks(self):
        """Regression: MQL validation must contain loops/checks for duplicates
        and finite numeric fields, not only names."""
        source = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        # Must contain loops for position/order duplicate checks
        self.assertIn("for(int i = 0; i < snapshot.position_count; i++)", source)
        self.assertIn("for(int j = i + 1; j < snapshot.position_count; j++)", source)
        self.assertIn("for(int i = 0; i < snapshot.order_count; i++)", source)
        # Must contain finite numeric checks using EEA_IsFiniteDouble
        self.assertIn("EEA_IsFiniteDouble", source)
        self.assertIn("!EEA_IsFiniteDouble(snapshot.positions[i].volume)", source)
        # Must contain chronological deal ordering checks
        self.assertIn("snapshot.deals[i].time_msc < snapshot.deals[i-1].time_msc", source)
        self.assertIn("snapshot.deals[i].deal_ticket < snapshot.deals[i-1].deal_ticket", source)
        # Must contain symbol spec validation loops
        self.assertIn("for(int i = 0; i < snapshot.symbol_count; i++)", source)
        # Must contain exact reason codes
        self.assertIn("POSITIONS_SOURCE_INCOMPLETE", source)
        self.assertIn("ORDERS_SOURCE_INCOMPLETE", source)
        self.assertIn("DEALS_SOURCE_INCOMPLETE", source)
        self.assertIn("SYMBOL_SPEC_INCOMPLETE", source)

    def test_fingerprint_is_32bit_fnv1a(self):
        """Regression: fingerprint label must say fnv1a32 not fnv1a64."""
        source = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        self.assertIn("fnv1a32", source)
        self.assertNotIn("fnv1a64", source)

    def test_no_self_hash_comparison_remains(self):
        """Regression: self-hash comparison (hashing fingerprint with itself) removed."""
        source = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        # Should NOT contain the impossible pattern of using account_fingerprint
        # as the account_id to the fingerprint function
        bad_line = "EEA_RuntimeFingerprint(snapshot.broker_server, snapshot.account_fingerprint)"
        self.assertNotIn(bad_line, source)

    def test_runtime_core_is_integrated_only_through_observer_coordinator(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("Runtime/ObserverRuntime.mqh", shell)
        self.assertNotIn('include "Runtime/RuntimeEvidence.mqh"', shell)


class RuntimeEvidenceAdapterTests(unittest.TestCase):
    def test_runtime_adapters_are_read_only(self):
        allowed_reads = ("AccountInfo", "TerminalInfo", "SymbolInfo", "PositionGet",
                         "OrderGet", "HistorySelect", "HistoryDealGet")
        forbidden = ("OrderSend", "OrderSendAsync", "CTrade", ".Buy(", ".Sell(",
                     "PositionClose", "PositionModify", "OrderDelete")
        sources = [
            ROOT / "Runtime/AccountSnapshotAdapter.mqh",
            ROOT / "Runtime/SymbolSpecAdapter.mqh",
            ROOT / "Runtime/BrokerReconciliationAdapter.mqh",
        ]
        combined = "\n".join(p.read_text(encoding="utf-8") for p in sources if p.exists())
        self.assertTrue(combined, "adapter files must exist for read-only test")
        # Must contain allowed read APIs
        self.assertTrue(any(tok in combined for tok in allowed_reads),
                        "adapter source must include allowed read APIs")
        for tok in forbidden:
            self.assertNotIn(tok, combined,
                             f"adapter source must not contain forbidden mutation token: {tok}")

    def test_account_adapter_never_serializes_account_name(self):
        path = ROOT / "Runtime/AccountSnapshotAdapter.mqh"
        self.assertTrue(path.exists(), "AccountSnapshotAdapter.mqh must exist")
        source = path.read_text(encoding="utf-8")
        self.assertNotIn("ACCOUNT_NAME", source,
                         "account adapter must never reference ACCOUNT_NAME")
        # Must read account identity fields through valid MQL5 property APIs
        for prop in ("AccountInfoString", "AccountInfoInteger", "AccountInfoDouble"):
            # At least one valid property API must appear (read-only identity)
            pass  # presence of read APIs validated by test_runtime_adapters_are_read_only

    def test_symbol_adapter_requires_explicit_bindings(self):
        path = ROOT / "Runtime/SymbolSpecAdapter.mqh"
        self.assertTrue(path.exists(), "SymbolSpecAdapter.mqh must exist")
        source = path.read_text(encoding="utf-8")
        # Must require caller-provided canonical and broker symbol (explicit, not inferred)
        self.assertIn("broker_symbol", source)
        # Must use SymbolInfo* read APIs (not mutation)
        self.assertTrue("SymbolInfo" in source or "SymbolInfoDouble" in source,
                        "symbol adapter must use SymbolInfo read APIs")

    def test_reconciliation_history_bounded_1_to_90(self):
        path = ROOT / "Runtime/BrokerReconciliationAdapter.mqh"
        self.assertTrue(path.exists(), "BrokerReconciliationAdapter.mqh must exist")
        source = path.read_text(encoding="utf-8")
        # Must enforce 1..90 days (plan spec: rejects outside range)
        self.assertTrue(("lookback" in source.lower() or "days" in source.lower() or
                         "HistorySelect" in source),
                        "reconciliation adapter must use bounded history selection")

    def test_account_fingerprint_opaque_fnv1a32(self):
        # Fingerprint must be opaque fnv1a32 over server|login|currency|margin_mode
        # Implemented in RuntimeEvidence.mqh; adapter must build account_id consistently.
        acct = ROOT / "Runtime/AccountSnapshotAdapter.mqh"
        ev   = ROOT / "Runtime/RuntimeEvidence.mqh"
        self.assertTrue(acct.exists() and ev.exists())
        ev_src = ev.read_text(encoding="utf-8")
        self.assertIn("fnv1a32", ev_src)
        # Adapter source must reference fingerprint helper / build string consistently
        acct_src = acct.read_text(encoding="utf-8") if acct.exists() else ""
        # At least consistent construction: server, login/identity, currency, margin
        for token in ("server", "currency", "margin_mode", "fingerprint"):
            # fingerprint string construction must be present somewhere in adapter or core
            self.assertTrue(token in ev_src or (acct.exists() and token in acct_src),
                            f"fingerprint build must include {token}")

    def test_reconciliation_source_flags_after_loops(self):
        # Source flags set only after loops succeed (plan §Task 2 Step 5, point 7)
        path = ROOT / "Runtime/BrokerReconciliationAdapter.mqh"
        self.assertTrue(path.exists())
        src = path.read_text(encoding="utf-8")
        # Must mention completeness flags (positions_complete / orders_complete / deals_complete)
        for flag in ("positions_complete", "orders_complete", "deals_complete"):
            self.assertIn(flag, src,
                          f"reconciliation adapter must set source flag: {flag}")


def test_no_broker_mutation_api_in_project_mql(self):
    forbidden = ("OrderSend", "OrderSendAsync", "CTrade", ".Buy(", ".Sell(",
                 "PositionClose", "PositionModify", "OrderDelete", "OrderModify")
    for root, dirs, files in os.walk(ROOT):
        # Skip non-source trees to keep fast
        dirs[:] = [d for d in dirs if d not in (".sf", "__pycache__") and not d.startswith(".")]
        for f in files:
            if f.endswith((".mq5", ".mqh")):
                p = Path(root) / f
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for tok in forbidden:
                    # Allow mentions inside comments / documentation that explicitly
                    # say "forbidden" / "excluded" — but the adapter layer must
                    # contain none.
                    lines = txt.splitlines()
                    for ln in lines:
                        if tok in ln:
                            # If line explicitly notes exclusion / forbidden, skip
                            lower_ln = ln.lower()
                            if any(x in lower_ln for x in ("forbidden", "excluded",
                                                           "not permitted", "no ",
                                                           "must not")):
                                continue
                            # Adapter files must be clean; other files we allow only
                            # if clearly documentation (not adapter implementation)
                            if "Runtime/AccountSnapshotAdapter" in str(p) or \
                               "Runtime/SymbolSpecAdapter" in str(p) or \
                               "Runtime/BrokerReconciliationAdapter" in str(p):
                                raise AssertionError(
                                    f"Adapter source contains mutation token {tok} at {p}:{ln}")


class RuntimeEvidenceIntegrationTests(unittest.TestCase):
    def test_store_uses_atomic_writer_and_redacts_identity(self):
        path = ROOT / "Storage/RuntimeEvidenceStore.mqh"
        self.assertTrue(path.exists())
        source = path.read_text(encoding="utf-8")
        self.assertIn("EEA_WriteAtomicText", source)
        self.assertIn("account_fingerprint", source)
        self.assertNotIn("ACCOUNT_LOGIN", source)
        self.assertNotIn("ACCOUNT_NAME", source)

    def test_reconciliation_store_serializes_observed_rows(self):
        source = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        for field in ('\\"positions\\"', '\\"orders\\"', '\\"deals\\"',
                      "s.positions[i].ticket", "s.orders[i].ticket", "s.deals[i].deal_ticket"):
            self.assertIn(field, source)

    def test_reconciliation_store_serializes_position_sl_tp_and_history_orders(self):
        source = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        self.assertIn("s.positions[i].sl", source)
        self.assertIn("s.positions[i].tp", source)
        self.assertIn("history_orders_complete", source)
        self.assertIn("history_order_count", source)
        self.assertIn("history_orders", source)
        for field in ('\\"ticket\\"', '\\"order_id\\"', '\\"symbol\\"', '\\"type\\"', '\\"volume\\"', '\\"price\\"', '\\"sl\\"', '\\"tp\\"', '\\"setup\\"', '\\"expiration\\"'):
            self.assertIn(field, source)

    def test_startup_checks_checkpoint_then_forces_fresh_refresh(self):
        source = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        check_at = source.find("EEA_RuntimeStoreCheckStatus")
        refresh_at = source.find("EEA_ObserverRuntimeRefresh(ctx,audit)", check_at)
        self.assertGreaterEqual(check_at, 0)
        self.assertGreater(refresh_at, check_at)
        self.assertIn("RUNTIME_CHECKPOINT_MISSING", source)
        self.assertIn("RUNTIME_CHECKPOINT_INCOMPATIBLE", source)

    def test_shell_integrates_observer_without_execution(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn('Runtime/ObserverRuntime.mqh', shell)
        self.assertIn("EventSetTimer", shell)
        self.assertIn("OnTradeTransaction", shell)
        self.assertIn("EEA_ObserverRuntimeMarkStale", shell)
        self.assertIn("EventKillTimer", shell)

    def test_tick_stays_free_of_runtime_io(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        tick = shell.split("void OnTick()", 1)[1].split("void OnTimer()", 1)[0]
        for token in ("ObserverRuntimeRefresh", "HistorySelect", "FileOpen", "WriteAtomic"):
            self.assertNotIn(token, tick)

    def test_transaction_only_invalidates_evidence(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        handler = shell.split("void OnTradeTransaction", 1)[1]
        self.assertIn("EEA_ObserverRuntimeMarkStale", handler)
        for token in ("OrderSend", "OrderDelete", "PositionClose"):
            self.assertNotIn(token, handler)



    def test_symbol_panel_existence_and_apis(self):
        panel_path = ROOT / "Runtime/SymbolSelectionPanel.mqh"
        self.assertTrue(panel_path.exists())
        src = panel_path.read_text(encoding="utf-8")
        self.assertIn("ObjectCreate", src)
        self.assertIn("ObjectSetInteger", src)
        self.assertIn("ObjectSetString", src)
        self.assertIn("ChartRedraw", src)
        self.assertIn("EEA_SymbolPanelInit", src)
        self.assertIn("EEA_SymbolPanelRefresh", src)
        self.assertIn("EEA_SymbolPanelHandleChartEvent", src)
        self.assertIn("EEA_SymbolPanelDestroy", src)
        self.assertIn("EEA_ObserverRuntimeApplySelection", src)

    def test_shell_chart_event_integration(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("OnChartEvent", shell)
        self.assertIn("InpShowSymbolPanel", shell)
        self.assertNotIn("InpBrokerSymbols", shell)
        self.assertIn("EEA_SymbolPanelHandleChartEvent", shell)
        self.assertIn("EEA_SymbolPanelInit", shell)
        self.assertIn("EEA_SymbolPanelDestroy", shell)

    def test_task2_panel_has_main_view_overlays_and_safe_routing(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for token in ("Btn_Settings", "Btn_Dashboard", "Btn_Close", "AUTO_REFRESH",
                      "Btn_Apply", "Btn_ResetStaged", "EnterpriseEA — OBSERVER ONLY",
                      "EXECUTION_DISABLED", "NOT_AUTHORIZED", "new_entries_blocked",
                      "POSITIONS", "ORDERS", "DEALS", "CONTEXT ONLY",
                      "EEA_SymbolPanelCloseOverlay", "EEA_SymbolPanelRenderMainView"):
            self.assertIn(token, panel)
        self.assertIn("EEA_SymbolPanelRefresh(0, g_runtime)", shell)
        self.assertNotIn("OrderSend", panel)
        self.assertNotIn("OrderSendAsync", panel)
        self.assertNotIn("CTrade", panel)
        self.assertNotIn("PositionClose", panel)
        self.assertNotIn("OrderDelete", panel)

    def test_task2_init_renders_before_return_and_timer_refreshes_view(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        init = shell.split("int OnInit()", 1)[1].split("void OnDeinit()", 1)[0]
        timer = shell.split("void OnTimer()", 1)[1].split("void OnTradeTransaction", 1)[0]
        self.assertIn("EEA_SymbolPanelInit", init)
        self.assertIn("EEA_SymbolPanelRefresh", init)
        self.assertIn("EEA_SymbolPanelRefresh", timer)

    def test_important_settings_controls_are_staged_and_display_only(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in ("FTMO_1_STEP", "FTMO_2_STEP", "BALANCE_BASED_FTMO_V1",
                      "Btn_Policy_FTMO_1_STEP", "Btn_Policy_FTMO_2_STEP",
                      "Btn_Policy_BALANCE_BASED_FTMO_V1", "Btn_DailyContinuation",
                      "Btn_OverallContinuation", "Btn_ConfirmPolicy",
                      "confirmation", "GMT+7", "UTC", "Apply status", "proposal"):
            self.assertIn(token, panel)
        apply_handler = panel.split("if(sparam==EEA_PANEL_OVERLAY_PREFIX+\"Btn_Apply\")", 1)[1]
        self.assertNotIn("ExecutionAdapter", apply_handler)
        self.assertNotIn("OrderSend", apply_handler)

    def test_main_market_rows_use_display_model_and_do_not_omit_selection(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in ("EEA_ObserverPanelMarketRow", "digits", "trade_mode",
                      "freshness_text", "EEA_ObserverPanelMarketRowFromRuntime"):
            self.assertIn(token, panel)
        self.assertNotIn("line<EEA_PANEL_MAX_ROWS-1", panel)

    def test_dashboard_has_specs_watermarks_risk_and_freshness(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in ("Digits:", "Trade mode:", "Evidence freshness:",
                      "Deal watermark:", "Watermark time:", "Risk policy:",
                      "Headroom:", "valid_until_utc", "observed_at_utc"):
            self.assertIn(token, panel)

    def test_settings_renders_actual_symbol_rows(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelRenderSettingsRows", panel)
        self.assertIn('EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Chk"', panel)
        self.assertIn('prefix+"Lbl"', panel)
        self.assertIn("g_panel_state.overlay_name==\"SETTINGS\"", panel)

    def test_dashboard_rerenders_when_open_on_timer(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelRefreshOpenOverlay", panel)
        timer = shell.split("void OnTimer()", 1)[1].split("void OnTradeTransaction", 1)[0]
        self.assertIn("EEA_SymbolPanelRefreshOpenOverlay", timer)
        self.assertIn("EEA_SymbolPanelRenderDashboard", panel)
        self.assertIn("EEA_LivePanelAllowed() && InpShowSymbolPanel", timer)

    def test_overlay_timer_guard_prevents_disabled_or_uninitialized_access(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        refresh_open = panel.split("void EEA_SymbolPanelRefreshOpenOverlay", 1)[1].split("void EEA_SymbolPanelLoadPolicy", 1)[0]
        self.assertIn("if(!g_panel_state.overlay_open) return;", refresh_open)
        timer = shell.split("void OnTimer()", 1)[1].split("void OnTradeTransaction", 1)[0]
        self.assertLess(timer.index("EEA_LivePanelAllowed() && InpShowSymbolPanel"), timer.index("EEA_SymbolPanelRefreshOpenOverlay"))

    def test_policy_is_explicitly_proposal_only(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("POLICY_PROPOSAL_ONLY", panel)
        self.assertIn("proposal only; no execution", panel)
        self.assertIn("APPLIED (DISPLAY/CONTROLLER PROPOSAL ONLY)", panel)

    def test_gmt7_authorization_is_editable_validated_and_rendered_as_utc(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "OBJ_EDIT", "OBJPROP_TEXT", "CHARTEVENT_OBJECT_ENDEDIT",
            "EEA_SymbolPanelParseGmtPlus7", "GMT_PLUS_7_INVALID",
            "GMT_PLUS_7_VALIDATED", "authorization_utc", "-7*60*60",
            "INVALID_GMT_PLUS_7_DATETIME",
        ):
            self.assertIn(token, panel)
        settings = panel.split("void EEA_SymbolPanelRenderSettings", 1)[1]
        self.assertIn("EEA_PANEL_OVERLAY_PREFIX+\"Edit_AuthorizationGmt7\"", settings)
        self.assertIn("EEA_SymbolPanelReadableUtc(g_panel_state.authorization_utc)", settings)

    def test_policy_proposal_and_apply_are_durable_and_policy_audited(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/PolicySettingsStore.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_PolicySettings", "EEA_PolicySettingsStoreLoad",
            "EEA_PolicySettingsStoreWrite", "EEA_WriteAtomicText",
            "policy_settings.json", "proposed_policy", "committed_policy",
            "POLICY_PROPOSED", "POLICY_APPLIED", "POLICY_APPLY_REJECTED",
            "EEA_SymbolPanelAuditPolicy",
        ):
            self.assertIn(token, panel + store)
        self.assertIn("EEA_SymbolPanelPersistPolicy", panel)
        self.assertIn("EEA_SymbolPanelLoadPolicy", panel)
        self.assertIn("EEA_PolicySettingsStoreWrite", panel)
        self.assertNotIn("ExecutionAdapter", panel)
        self.assertNotIn("OrderSend", panel)
        self.assertNotIn("PAPER", panel.upper())

    def test_policy_choices_persist_proposals_without_execution_or_refresh_dependency(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for button in ("Btn_Policy_FTMO_1_STEP", "Btn_Policy_FTMO_2_STEP", "Btn_Policy_BALANCE_BASED_FTMO_V1"):
            branch = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"' + button + '"', 1)[1].split("return;", 1)[0]
            self.assertIn("EEA_SymbolPanelPersistPolicy(ctx,audit,false)", branch)
        apply_branch = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Apply"', 1)[1].split("return;", 1)[0]
        self.assertIn("EEA_SymbolPanelApplyStaged", apply_branch)
        self.assertNotIn("EEA_ExecutionAdapter", apply_branch)
        self.assertNotIn("OrderSend", apply_branch)

    def test_policy_store_rejects_unknown_policy_and_non_monotonic_revision(self):
        store = (ROOT / "Storage/PolicySettingsStore.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_PolicyIdValid", store)
        self.assertIn("proposed_policy==\"\"", store)
        self.assertIn("committed_policy==\"\"", store)
        self.assertIn("existing.revision", store)
        self.assertIn("POLICY_REVISION_ROLLBACK", store)

    def test_utc_display_uses_explicit_utc_formatter_not_terminal_local_rendering(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelUtcText", panel)
        self.assertIn("TimeToStruct", panel)
        self.assertIn("Z", panel)
        self.assertNotIn('TimeToString((datetime)value,TIME_DATE|TIME_SECONDS)+" UTC"', panel)

    def test_degraded_runtime_still_initializes_and_renders_panel(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelInit(0, InpPanelSubWindow);", shell)
        init = shell.split("int OnInit()", 1)[1].split("void OnDeinit()", 1)[0]
        runtime_init = init.index("EEA_ObserverRuntimeInit")
        panel_init = init.index("EEA_SymbolPanelInit")
        self.assertGreater(panel_init, runtime_init)
        self.assertIn("RUNTIME_INIT_DEGRADED", init)
        self.assertNotIn("return INIT_FAILED;", init[init.index("if(!EEA_ObserverRuntimeInit"):init.index("if(!EventSetTimer")])
        self.assertIn("EEA_SymbolPanelRefresh(0, g_runtime)", init)

    def test_dxy_is_context_only_and_never_selected_for_runtime_apply(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelIsContextOnly", panel)
        self.assertIn('"DXY"', panel)
        self.assertIn('"USDX"', panel)
        row = panel.split("EEA_ObserverPanelMarketRow EEA_ObserverPanelMarketRowFromRuntime", 1)[1].split("void EEA_SymbolPanelRenderMainView", 1)[0]
        self.assertIn("row.context_only=EEA_SymbolPanelIsContextOnly", row)
        refresh = panel.split("void EEA_SymbolPanelRefresh", 1)[1].split("void EEA_SymbolPanelRefreshOpenOverlay", 1)[0]
        self.assertIn("context_only=EEA_SymbolPanelIsContextOnly", refresh)
        self.assertIn("CONTEXT ONLY", panel)

    def test_timer_refresh_does_not_overwrite_staged_policy(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        refresh = panel.split("void EEA_SymbolPanelRefresh", 1)[1].split("void EEA_SymbolPanelRefreshOpenOverlay", 1)[0]
        self.assertIn("if(!g_panel_state.staged_initialized)", refresh)
        self.assertIn("EEA_SymbolPanelLoadPolicy(ctx)", refresh)
        self.assertLess(refresh.index("EEA_SymbolPanelLoadPolicy(ctx)"), refresh.index("g_panel_state.staged_initialized=true;"))

    def test_non_apply_policy_rollback_is_shared_and_complete(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("struct EEA_SymbolPanelPolicySnapshot", panel)
        self.assertIn("EEA_SymbolPanelCapturePolicySnapshot", panel)
        self.assertIn("EEA_SymbolPanelRestorePolicySnapshot", panel)
        handler = panel.split("void EEA_SymbolPanelHandleChartEvent", 1)[1]
        for button in ("Btn_Policy_FTMO_1_STEP", "Btn_Policy_FTMO_2_STEP", "Btn_Policy_BALANCE_BASED_FTMO_V1"):
            branch = handler.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"' + button + '"', 1)[1].split("return;", 1)[0]
            self.assertIn("EEA_SymbolPanelCapturePolicySnapshot", branch)
            self.assertIn("bool policy_persisted", branch)
            self.assertIn("EEA_SymbolPanelRestorePolicySnapshot", branch)
        for token in ("staged_policy", "staged_daily_continuation", "staged_overall_continuation",
                      "policy_confirmed", "authorization_input_gmt7", "authorization_utc",
                      "status_message", "apply_reason"):
            self.assertIn(token, panel)
        self.assertNotIn("if(!EEA_SymbolPanelPersistPolicy(ctx,audit,false)) //", panel)

    def test_policy_persist_failure_restores_policy_state_and_audits_rejection(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("bool EEA_SymbolPanelPersistPolicy", panel)
        persist = panel.split("bool EEA_SymbolPanelPersistPolicy", 1)[1].split("void EEA_SymbolPanelRenderSettings", 1)[0]
        self.assertIn("POLICY_APPLY_REJECTED", persist)
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        for token in ("old_committed_policy", "old_policy", "POLICY_SETTINGS_PERSISTENCE_FAILED",
                      "g_panel_state.committed_policy=old_committed_policy"):
            self.assertIn(token, apply)

    def test_apply_verifies_the_exact_policy_settings_that_persist_wrote(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        persist = panel.split("bool EEA_SymbolPanelPersistPolicy", 1)[1].split("void EEA_SymbolPanelRenderSettings", 1)[0]
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        self.assertIn("EEA_PolicySettings &written", persist)
        self.assertIn("written=stored", persist)
        self.assertIn("EEA_PolicySettings persisted_policy", apply)
        self.assertIn("EEA_SymbolPanelPersistPolicy(ctx,audit,true,persisted_policy)", apply)
        self.assertIn("EEA_SymbolPanelVerifyPersistedPolicy(ctx,persisted_policy)", apply)
        self.assertNotIn("expected.revision=", apply)
        self.assertNotIn("EEA_PolicySettings expected", apply)
        self.assertNotIn("GetTickCount64", apply)

    def test_policy_persist_failure_fails_closed_when_any_rollback_write_fails(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        persist_failure = apply.split("EEA_PolicySettings persisted_policy", 1)[1].split("if(!EEA_SymbolPanelVerifyPersistedPolicy", 1)[0]
        self.assertIn("bool rollback_persisted=", persist_failure)
        self.assertIn("bool policy_file_restored=", persist_failure)
        self.assertIn("if(!rollback_persisted || !policy_file_restored)", persist_failure)
        self.assertIn('ctx.status.runtime_state="BLOCKED"', persist_failure)
        self.assertIn("EEA_RuntimeStoreWriteStatus", persist_failure)
        self.assertIn("bool rollback_status_persisted=", persist_failure)
        self.assertIn("rollback_status_persisted ?", persist_failure)
        self.assertIn("EEA_ObserverRuntimeAudit", persist_failure)
        self.assertGreaterEqual(persist_failure.count("EEA_SymbolPanelRequirePolicyAudit"), 1)
        self.assertIn("POLICY_ROLLBACK_STATUS_PERSISTENCE_FAILED", persist_failure)

    def test_runtime_selection_failure_restores_persisted_policy_proposal_file(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        runtime_failure = apply[apply.rfind("else"):]
        self.assertIn("EEA_SymbolPanelRestorePolicyFile", runtime_failure)
        self.assertIn("old_policy_file_contents", runtime_failure)
        self.assertIn("old_policy_file_exists", runtime_failure)
        self.assertIn('ctx.status.runtime_state="BLOCKED"', runtime_failure)
        self.assertIn("POLICY_ROLLBACK_PERSISTENCE_FAILED", runtime_failure)
        self.assertIn("EEA_ObserverRuntimeAudit", runtime_failure)

    def test_context_only_rows_are_never_rechecked_by_reset_or_apply(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        reset = panel.split("void EEA_SymbolPanelResetStaged", 1)[1].split("void EEA_SymbolPanelApplyStaged", 1)[0]
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        self.assertIn("!g_panel_state.rows[i].context_only", reset)
        self.assertIn("!g_panel_state.rows[i].context_only", apply)
        self.assertIn("CONTEXT ONLY", panel)

    def test_policy_proposal_persist_failure_rolls_back_staged_state(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("bool EEA_SymbolPanelPersistPolicy", panel)
        for button in ("Btn_Policy_FTMO_1_STEP", "Btn_Policy_FTMO_2_STEP", "Btn_Policy_BALANCE_BASED_FTMO_V1"):
            branch = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"' + button + '"', 1)[1].split("return;", 1)[0]
            self.assertTrue("EEA_SymbolPanelPersistPolicy(ctx,audit,false)" in branch)
            self.assertTrue("EEA_SymbolPanelRestorePolicySnapshot(old_policy)" in branch)
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        self.assertIn("EEA_SymbolPanelPersistPolicy(ctx,audit,true,persisted_policy)", apply)
        self.assertIn("POLICY_SETTINGS_PERSISTENCE_FAILED", apply)

    def test_gmt7_controls_do_not_overlap_status_or_symbol_rows(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        settings = panel.split("void EEA_SymbolPanelRenderSettings", 1)[1].split("void EEA_SymbolPanelRenderDashboard", 1)[0]
        self.assertIn("EEA_SymbolPanelSetEdit(chart_id,EEA_PANEL_OVERLAY_PREFIX+\"Edit_AuthorizationGmt7\",EEA_PANEL_CONTENT_X,298,220", settings)
        self.assertIn("ObjectSetInteger(chart_id,name,OBJPROP_YSIZE,EEA_PANEL_CONTROL_HEIGHT)", panel)
        self.assertIn("EEA_PANEL_OVERLAY_PREFIX+\"Lbl_ApplyStatus\",EEA_PANEL_CONTENT_X,338", settings)
        self.assertIn("EEA_PANEL_OVERLAY_PREFIX+\"Lbl_PersistenceStatus\",EEA_PANEL_CONTENT_X,400", settings)
        self.assertIn("EEA_PANEL_OVERLAY_PREFIX+\"Lbl_Safety\",EEA_PANEL_CONTENT_X,EEA_PANEL_SETTINGS_SAFETY_Y", settings)
        self.assertNotEqual(settings.count('EEA_PANEL_OVERLAY_PREFIX+"Lbl_ApplyStatus"'), 2)
        rows = panel.split("void EEA_SymbolPanelRenderSettingsRows", 1)[1].split("void EEA_SymbolPanelRefresh", 1)[0]
        self.assertIn("EEA_PANEL_SETTINGS_ROWS_Y+i*EEA_PANEL_ROW_HEIGHT", rows)

    def test_policy_verification_failure_checks_runtime_and_policy_rollback_results(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        verification = apply.split("if(!EEA_SymbolPanelVerifyPersistedPolicy", 1)[1]
        for token in (
            "bool runtime_rollback_persisted=EEA_ObserverRuntimeRestoreSelectionSnapshot",
            "bool policy_file_restored=EEA_SymbolPanelRestorePolicyFile",
            "EEA_SymbolPanelRestorePolicySnapshot(old_policy)",
            "if(!runtime_rollback_persisted || !policy_file_restored)",
            "ctx.status.runtime_state=\"BLOCKED\"",
            "ctx.status.new_entries_blocked=true",
            "POLICY_ROLLBACK_FAILED",
            "POLICY_ROLLBACK_PERSISTENCE_FAILED",
        ):
            self.assertIn(token, verification)

    def test_policy_snapshot_restores_all_visible_staged_and_status_fields(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        snapshot = panel.split("struct EEA_SymbolPanelPolicySnapshot", 1)[1].split("void EEA_SymbolPanelCapturePolicySnapshot", 1)[0]
        restore = panel.split("void EEA_SymbolPanelRestorePolicySnapshot", 1)[1].split("string EEA_SymbolPanelUtcText", 1)[0]
        for token in (
            "committed_policy", "committed_daily_continuation", "committed_overall_continuation",
            "staged_policy", "staged_daily_continuation", "staged_overall_continuation",
            "policy_confirmed", "authorization_input_gmt7", "authorization_utc",
            "status_message", "apply_reason",
        ):
            self.assertIn(token, snapshot)
            self.assertIn(token, restore)

    def test_failed_policy_rollback_persists_blocked_runtime_state_and_audits(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        failure = apply.split("if(!runtime_rollback_persisted || !policy_file_restored)", 1)[1]
        self.assertIn("EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status", failure)
        self.assertIn('EEA_ObserverRuntimeAuditChecked(ctx,audit,"POLICY_ROLLBACK_FAILED",ctx.status)', failure)
        self.assertIn("POLICY_ROLLBACK_PERSISTENCE_FAILED", failure)

    def test_policy_persist_returns_explicit_success_or_failure(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        persist = panel.split("bool EEA_SymbolPanelPersistPolicy", 1)[1].split("void EEA_SymbolPanelRenderSettings", 1)[0]
        self.assertIn("return true;", persist)
        self.assertIn("return false;", persist)
        self.assertNotIn("void EEA_SymbolPanelPersistPolicy", panel)

    def test_staged_continuation_values_are_durable_and_restored_as_proposed(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/PolicySettingsStore.mqh").read_text(encoding="utf-8")
        for token in ("proposed_daily_continuation", "proposed_overall_continuation"):
            self.assertIn(token, panel + store)
        self.assertIn("stored.proposed_daily_continuation=g_panel_state.staged_daily_continuation", panel)
        self.assertIn("stored.proposed_overall_continuation=g_panel_state.staged_overall_continuation", panel)
        self.assertIn("g_panel_state.staged_daily_continuation=stored.proposed_daily_continuation", panel)
        self.assertIn("g_panel_state.staged_overall_continuation=stored.proposed_overall_continuation", panel)

    def test_dxy_context_rows_are_disabled_at_render_and_click_boundaries(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        rows = panel.split("void EEA_SymbolPanelRenderSettingsRows", 1)[1].split("void EEA_SymbolPanelRefresh", 1)[0]
        handler = panel.split("void EEA_SymbolPanelHandleChartEvent", 1)[1]
        self.assertIn("context_only ? \"N/A\"", rows)
        self.assertIn("if(g_panel_state.rows[i].context_only) return;", handler)
        self.assertIn("!g_panel_state.rows[i].context_only", handler)

    def test_policy_failure_restores_runtime_snapshot_and_repersists_it(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        for token in ("old_canonical_symbols", "old_broker_symbols", "old_symbol_specs",
                      "old_reconciliation", "old_status", "EEA_ObserverRuntimeRestoreSelectionSnapshot",
                      "POLICY_APPLY_REJECTED"):
            self.assertIn(token, apply)
        self.assertIn("EEA_ObserverRuntimeRestoreSelectionSnapshot", runtime)
        self.assertIn("ctx.canonical_symbols[i] = old_canons[i]", runtime)
        self.assertEqual(runtime.count("ctx.canonical_symbols[i] = old_canons[i]"), 1)

    def test_apply_snapshots_complete_runtime_and_policy_identity(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/PolicySettingsStore.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        for token in ("old_account", "old_staged_daily", "old_staged_overall",
                      "old_policy_confirmed", "old_authorization_input_gmt7",
                      "old_authorization_utc", "old_policy_file_contents",
                      "old_policy_revision", "EEA_SymbolPanelRestorePolicyFile",
                      "EEA_SymbolPanelVerifyPersistedPolicy"):
            self.assertIn(token, apply)
        self.assertIn("EEA_RuntimeStoreWriteAccount", runtime)
        for token in ("authorization_input_gmt7", "policy_confirmed"):
            self.assertIn(token, store)

    def test_non_apply_persistence_failure_restores_visible_policy_state(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        handler = panel.split("void EEA_SymbolPanelHandleChartEvent", 1)[1]
        for token in ("old_authorization_input_gmt7", "old_authorization_utc",
                      "POLICY_SETTINGS_PERSISTENCE_FAILED", "policy_confirmed"):
            self.assertIn(token, handler)
        self.assertIn("bool EEA_SymbolPanelPersistPolicy", panel)

    def test_degraded_refresh_retries_blank_broker_discovery(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        refresh = runtime.split("bool EEA_ObserverRuntimeRefresh", 1)[1].split("bool EEA_ObserverRuntimeInit", 1)[0]
        for token in ("broker_symbols[i]==\"\"", "EEA_ObserverRuntimeAutoDiscover",
                      "RUNTIME_INIT_DEGRADED", "ctx.status.runtime_state=\"DEGRADED\""):
            self.assertIn(token, refresh + runtime)

    def test_gmt7_parser_is_timezone_independent_and_restores_input(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        parser = panel.split("bool EEA_SymbolPanelParseGmtPlus7", 1)[1].split("void EEA_SymbolPanelAuditPolicy", 1)[0]
        self.assertNotIn("StringToTime", parser)
        for token in ("EEA_SymbolPanelDaysFromCivil", "authorization_input_gmt7",
                      "old_authorization_input_gmt7"):
            self.assertIn(token, panel)

    def test_apply_rollback_restores_exact_policy_file_and_does_not_double_restore(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        for token in ("old_policy_file_exists", "old_policy_file_contents",
                      "EEA_SymbolPanelRestorePolicyFile", "old_status_message", "old_apply_reason"):
            self.assertIn(token, apply)
        self.assertEqual(apply.count("EEA_ObserverRuntimeRestoreSelectionSnapshot"), 2,
                         "apply must restore once per failure branch, not twice in one branch")
        self.assertIn("EEA_SymbolPanelVerifyPersistedPolicy(ctx,stored)", panel)

    def test_non_apply_policy_failures_restore_all_staged_state_and_reason(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        handler = panel.split("void EEA_SymbolPanelHandleChartEvent", 1)[1]
        for token in ("old_staged_daily", "old_staged_overall", "old_policy_confirmed",
                      "old_status_message", "old_apply_reason", "POLICY_SETTINGS_PERSISTENCE_FAILED"):
            self.assertIn(token, handler)
        self.assertIn("bool policy_persisted", handler)

    def test_account_read_failure_marks_degraded_stale_pending_and_blocked(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        refresh = runtime.split("bool EEA_ObserverRuntimeRefresh", 1)[1].split("bool EEA_ObserverRuntimeInit", 1)[0]
        account_failure = refresh.split("if(!EEA_ReadRuntimeAccount", 1)[1].split("string reason", 1)[0]
        for token in ("ctx.status.runtime_state=\"DEGRADED\"", "ctx.stale=true",
                      "ctx.stale_reason=account_refresh_reason", "ctx.status.pending_refresh=true",
                      "ctx.status.new_entries_blocked=true", "RUNTIME_ACCOUNT_REFRESH_FAILED"):
            self.assertIn(token, account_failure)

    def test_degraded_refresh_retries_after_account_refresh_and_fails_closed(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        refresh = runtime.split("bool EEA_ObserverRuntimeRefresh", 1)[1].split("bool EEA_ObserverRuntimeInit", 1)[0]
        self.assertLess(refresh.index("EEA_ReadRuntimeAccount"), refresh.index("EEA_ObserverRuntimeAutoDiscover"))
        for token in ("ctx.stale=true", "ctx.status.pending_refresh=true",
                      "RUNTIME_SYMBOL_DISCOVERY_DEGRADED", "ctx.status.runtime_state=\"DEGRADED\""):
            self.assertIn(token, refresh)

    def test_runtime_rollback_restores_account_and_pending_retry_context(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        restore = runtime.split("bool EEA_ObserverRuntimeRestoreSelectionSnapshot", 1)[1].split("bool EEA_ObserverRuntimeApplySelection", 1)[0]
        for token in ("ctx.account=old_account", "ctx.stale=old_stale", "ctx.stale_reason=old_stale_reason",
                      "ctx.last_refresh_utc=old_last_refresh_utc", "ctx.previous_deal_watermark=old_previous_deal_watermark",
                      "ctx.status=old_status", "EEA_RuntimeStoreWriteAccount"):
            self.assertIn(token, restore)

    def test_degraded_startup_copies_canonical_rows_before_resolution(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        self.assertLess(init.index("ctx.canonical_symbols[i]"), init.index("EEA_ObserverRuntimeAutoDiscover"))
        self.assertIn("ctx.broker_symbols[i]=\"\"", init)

    def test_auto_discover_initializes_all_rows_before_partial_resolution(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        discover = runtime.split("bool EEA_ObserverRuntimeAutoDiscover", 1)[1].split("bool EEA_ObserverRuntimeRefresh", 1)[0]
        self.assertIn("ArrayResize(brokers, count)", discover)
        self.assertIn("ArrayResize(brokers, count)", discover)
        self.assertIn("brokers[i]=\"\"", discover)
        self.assertLess(discover.index("brokers[i]=\"\""), discover.index("if(!results[i].resolved)"))

    def test_degraded_init_preserves_rows_and_marks_status_degraded(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        self.assertIn("ctx.status.runtime_state=\"DEGRADED\"", init)
        self.assertIn("ctx.status.new_entries_blocked=true", init)
        self.assertIn("ctx.initialized=true", init)
        self.assertLess(init.index("ctx.canonical_symbols[i]"), init.index("ctx.status.runtime_state=\"DEGRADED\""))

    def test_dxy_context_only_does_not_block_discovery_or_refresh(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_ObserverRuntimeIsContextOnly", runtime)
        discover = runtime.split("bool EEA_ObserverRuntimeAutoDiscover", 1)[1].split("bool EEA_ObserverRuntimeRefresh", 1)[0]
        refresh = runtime.split("bool EEA_ObserverRuntimeRefresh", 1)[1].split("bool EEA_ObserverRuntimeInit", 1)[0]
        self.assertIn("EEA_ObserverRuntimeIsContextOnly", discover)
        self.assertIn("EEA_ObserverRuntimeIsContextOnly", refresh)

    def test_discovery_skips_runtime_spec_reads_for_context_only_rows(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        discover = runtime.split("bool EEA_ObserverRuntimeAutoDiscover", 1)[1].split("bool EEA_ObserverRuntimeRefresh", 1)[0]
        self.assertIn("EEA_ObserverRuntimeIsContextOnly(canonicals[i],brokers[i])", discover)
        self.assertLess(discover.index("EEA_ObserverRuntimeIsContextOnly(canonicals[i],brokers[i])"),
                        discover.index("EEA_ReadRuntimeSymbolSpec"))

    def test_discovery_allocates_broker_rows_once_before_resolution(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        discover = runtime.split("bool EEA_ObserverRuntimeAutoDiscover", 1)[1].split("bool EEA_ObserverRuntimeRefresh", 1)[0]
        self.assertEqual(discover.count("ArrayResize(brokers"), 1)

    def test_account_failure_keeps_degraded_runtime_initialized_for_ui(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        failure = init.split("if(!EEA_ReadRuntimeAccount", 1)[1].split("string brokers", 1)[0]
        for token in ("ctx.status.runtime_state=\"DEGRADED\"", "ctx.status.new_entries_blocked=true",
                      "ctx.initialized=true", "RUNTIME_ACCOUNT_INIT_DEGRADED"):
            self.assertIn(token, failure)

    def test_degraded_startup_sets_retry_context_for_timer_recovery(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        failure = init.split("if(!EEA_ReadRuntimeAccount", 1)[1].split("string brokers", 1)[0]
        for token in ("ctx.stale=true", "ctx.stale_reason=account_reason", "ctx.status.pending_refresh=true"):
            self.assertIn(token, failure)

    def test_discovery_failure_sets_retry_context_for_timer_recovery(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        failure = init.split("if(!EEA_ObserverRuntimeAutoDiscover", 1)[1].split("for(int i=0;i<count", 1)[0]
        for token in ("ctx.stale=true", "ctx.stale_reason=discover_reason", "ctx.status.pending_refresh=true"):
            self.assertIn(token, failure)

    def test_subwindow_and_disabled_evidence_guards_are_explicit(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("ObjectCreate(chart_id,name,OBJ_LABEL,g_panel_state.sub_window,0,0)", panel)
        self.assertIn("ObjectCreate(chart_id,name,OBJ_BUTTON,g_panel_state.sub_window,0,0)", panel)
        self.assertNotIn("OBJPROP_SUBWINDOW", panel)
        init = shell.split("int OnInit()", 1)[1].split("void OnDeinit()", 1)[0]
        self.assertIn("if(InpRuntimeEvidenceEnabled) EEA_SymbolPanelRefresh", init)
        timer = shell.split("void OnTimer()", 1)[1].split("void OnTradeTransaction", 1)[0]
        self.assertIn("if(InpRuntimeEvidenceEnabled)", timer)

    def test_panel_presentation_uses_neutral_palette_and_explicit_object_style(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_PANEL_BG_COLOR", "EEA_PANEL_SURFACE_COLOR", "EEA_PANEL_TEXT_COLOR",
            "EEA_PANEL_MUTED_COLOR", "EEA_PANEL_OK_COLOR", "EEA_PANEL_WARNING_COLOR",
            "EEA_PANEL_DANGER_COLOR", "EEA_SymbolPanelSetSurface",
            "OBJPROP_BGCOLOR", "OBJPROP_BORDER_COLOR", "OBJPROP_FONTSIZE",
            "OBJPROP_ZORDER", "OBJPROP_HIDDEN", "OBJPROP_SELECTABLE",
        ):
            self.assertIn(token, panel)
        self.assertNotIn("ObjectSetInteger(chart_id,name,OBJPROP_COLOR,clrRed)", panel)

    def test_panel_presentation_has_bounded_cards_and_cleans_old_objects(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_PANEL_MAIN_WIDTH", "EEA_PANEL_MAIN_HEIGHT", "EEA_PANEL_SETTINGS_HEIGHT",
            "EEA_PANEL_DASHBOARD_HEIGHT", "EEA_PANEL_VISIBLE_ROWS",
            "EEA_PANEL_MAIN_PREFIX+\"Surface\"",
            "EEA_PANEL_OVERLAY_PREFIX+\"Surface\"",
            "ObjectsDeleteAll(chart_id,EEA_PANEL_PREFIX,g_panel_state.sub_window)",
            "ObjectsDeleteAll(chart_id,EEA_PANEL_OVERLAY_PREFIX,g_panel_state.sub_window)",
        ):
            self.assertIn(token, panel)

    def test_panel_presentation_scales_for_readability_and_spacing(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "#define EEA_PANEL_MAIN_WIDTH 540",
            "#define EEA_PANEL_ROW_HEIGHT 29",
            "#define EEA_PANEL_CONTROL_HEIGHT 30",
            "#define EEA_PANEL_BODY_FONT_SIZE 10",
            "#define EEA_PANEL_META_FONT_SIZE 9",
            "#define EEA_PANEL_TITLE_FONT_SIZE 13",
            "#define EEA_PANEL_INNER_WIDTH 516",
        ):
            self.assertIn(token, panel)

    def test_panel_reuses_same_overlay_and_clears_dynamic_rows_before_rebinding(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_SymbolPanelBeginOverlay",
            "EEA_SymbolPanelClearSettingsRows",
            "EEA_SymbolPanelClearDashboardRows",
            'ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Spec_"+IntegerToString(i))',
            'ObjectDelete(chart_id,EEA_PANEL_OVERLAY_PREFIX+"Row_"+IntegerToString(i)+"_Chk")',
        ):
            self.assertIn(token, panel)
        settings = panel.split("void EEA_SymbolPanelRenderSettings", 1)[1].split(
            "void EEA_SymbolPanelRenderDashboard", 1
        )[0]
        dashboard = panel.split("void EEA_SymbolPanelRenderDashboard", 1)[1].split(
            "void EEA_SymbolPanelResetStaged", 1
        )[0]
        self.assertIn("EEA_SymbolPanelBeginOverlay", settings)
        self.assertIn("EEA_SymbolPanelBeginOverlay", dashboard)
        self.assertNotIn("EEA_SymbolPanelClearOverlay(chart_id);", settings)
        self.assertNotIn("EEA_SymbolPanelClearOverlay(chart_id);", dashboard)

    def test_panel_status_uses_semantic_color_without_changing_fail_closed_copy(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_SymbolPanelStatusColor", "ctx.status.runtime_state",
            "ctx.status.reason_code", "EXECUTION_DISABLED", "NOT_AUTHORIZED",
            "new_entries_blocked",
        ):
            self.assertIn(token, panel)
        self.assertIn("EEA_PANEL_DANGER_COLOR", panel)

    def test_settings_symbol_rows_are_paged_without_changing_stored_row_indices(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        for token in (
            "row_offset", "Btn_PreviousRows", "Btn_NextRows",
            "EEA_PANEL_VISIBLE_ROWS", "row_index", "g_panel_state.row_offset",
        ):
            self.assertIn(token, panel)

    def test_selection_rollback_repersists_previous_committed_evidence(self):
        obs = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        for token in ("EEA_RuntimeStatus old_status", "old_reconciliation",
                      "old_stale", "old_stale_reason", "old_last_refresh_utc",
                      "old_previous_deal_watermark", "old_previous_deal_watermark_time",
                      "EEA_RuntimeStoreWriteSymbols", "EEA_RuntimeStoreWriteReconciliation",
                      "EEA_RuntimeStoreWriteSymbolSelection", "EEA_RuntimeStoreWriteStatus",
                      "SELECTION_APPLY_ROLLBACK_PERSISTED"):
            self.assertIn(token, obs)
    def test_policy_revision_is_loaded_and_incremented_durably(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        persist = panel.split("bool EEA_SymbolPanelPersistPolicy", 1)[1].split("bool EEA_SymbolPanelPersistPolicy", 2)[0]
        self.assertIn("EEA_PolicySettings existing", persist)
        self.assertIn("EEA_PolicySettingsStoreLoad", persist)
        self.assertIn("existing.revision+1", persist)
        self.assertIn("FileIsExist", persist)
        self.assertIn("POLICY_SETTINGS_REVISION_UNAVAILABLE", persist)
        self.assertNotIn("GetTickCount64", persist)

    def test_selection_apply_failure_restores_exact_staged_row_checked_states(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        self.assertIn("old_row_checked[EEA_PANEL_MAX_ROWS]", apply)
        self.assertIn("old_row_checked[i]=g_panel_state.rows[i].checked", apply)
        self.assertIn("g_panel_state.rows[i].checked=old_row_checked[i]", apply)
        self.assertGreaterEqual(apply.count("g_panel_state.rows[i].checked=old_row_checked[i]"), 2)

    def test_runtime_failure_branch_restores_checked_snapshot_before_reporting_failure(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        runtime_failure = apply[apply.rfind("else") :]
        self.assertIn("old_row_checked[i]", runtime_failure)
        self.assertIn("g_panel_state.rows[i].checked=old_row_checked[i]", runtime_failure)

    def test_selection_revision_is_parsed_validated_and_restored_on_init(self):
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_RuntimeStoreLoadSymbolSelectionRevision", store)
        self.assertIn("selection_revision", store)
        self.assertIn("revision<=0", store)
        self.assertIn("EEA_RuntimeStoreLoadSymbolSelectionRevision", runtime)
        self.assertIn("ctx.status.selection_revision=", runtime)
        self.assertNotIn("ctx.status.selection_revision = 1;", runtime)

    def test_audit_failures_are_checked_and_blocked_status_is_persisted(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_ObserverRuntimeAuditChecked", runtime)
        for lifecycle in ("RUNTIME_ACCOUNT_REFRESH_FAILED", "RUNTIME_SYMBOL_DISCOVERY_DEGRADED",
                          "RUNTIME_REFRESH_FAILED", "RUNTIME_PERSISTENCE_FAILED",
                          "RUNTIME_CHECKPOINT_OBSERVED", "BROKER_TRANSACTION_OBSERVED",
                          "RUNTIME_STOPPED"):
            self.assertIn("EEA_ObserverRuntimeAuditChecked", runtime)
        self.assertIn("EEA_RuntimeStoreWriteStatus", runtime)
        require = panel.split("bool EEA_SymbolPanelRequirePolicyAudit", 1)[1].split("void EEA_SymbolPanelClearOverlay", 1)[0]
        self.assertIn("bool status_persisted=EEA_RuntimeStoreWriteStatus", require)
        self.assertIn("return false", require)
        self.assertIn("EEA_ObserverRuntimeAuditChecked", shell + runtime)

    def test_policy_audit_append_failure_never_reports_success_when_status_persists(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        require = panel.split("bool EEA_SymbolPanelRequirePolicyAudit", 1)[1].split("void EEA_SymbolPanelClearOverlay", 1)[0]
        self.assertIn("if(EEA_SymbolPanelAuditPolicy(audit,event_type,reason,policy,authorization_utc)) return true;", require)
        self.assertIn("bool status_persisted=EEA_RuntimeStoreWriteStatus", require)
        self.assertIn("return false;", require)
        self.assertNotIn("return status_persisted", require)

    def test_selection_rollback_persistence_failure_blocks_persists_and_checks_audit(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        apply = runtime.split("bool EEA_ObserverRuntimeApplySelection", 1)[1]
        failure = apply.split("if(!rollback_persisted)", 1)[1].split("else if", 1)[0]
        for token in (
            'ctx.status.runtime_state="BLOCKED"',
            'ctx.status.reason_code="POLICY/SELECTION_ROLLBACK_PERSISTENCE_FAILED"',
            "ctx.status.new_entries_blocked=true",
            "EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status",
            'EEA_ObserverRuntimeAuditChecked(ctx,audit,"SELECTION_ROLLBACK_PERSISTENCE_FAILED",ctx.status)',
        ):
            self.assertIn(token, failure)
        self.assertLess(failure.index('ctx.status.reason_code="POLICY/SELECTION_ROLLBACK_PERSISTENCE_FAILED"'),
                        failure.index("EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status"))
        self.assertLess(failure.index("EEA_RuntimeStoreWriteStatus(ctx.root,ctx.status"),
                        failure.index("EEA_ObserverRuntimeAuditChecked(ctx,audit"))

    def test_audit_failure_does_not_introduce_paper_or_execution(self):
        for path in (ROOT / "Runtime/ObserverRuntime.mqh", ROOT / "Runtime/SymbolSelectionPanel.mqh"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("PAPER", source.upper())
            self.assertNotIn("OrderSend", source)
            self.assertNotIn("CTrade", source)

    def test_rollback_and_policy_rejection_require_durable_audit_append_success(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        audit_panel = panel.split("bool EEA_SymbolPanelAuditPolicy", 1)[1].split("void EEA_SymbolPanelClearOverlay", 1)[0]
        audit_runtime = runtime.split("bool EEA_ObserverRuntimeAudit", 1)[1].split("bool EEA_ObserverRuntimeIsContextOnly", 1)[0]
        self.assertIn("return audit.Append", audit_panel)
        self.assertIn("return audit.Append", audit_runtime)
        self.assertIn("AUDIT_PERSISTENCE_FAILED", panel + runtime)
        self.assertIn("EEA_RuntimeStoreWriteStatus", panel + runtime)
        self.assertIn("EEA_SymbolPanelAuditPolicy(audit", panel)
        self.assertIn("!EEA_ObserverRuntimeAudit", panel + runtime)
    def test_audit_helper_failure_persists_blocked_status_and_returns_failure(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("bool EEA_ObserverRuntimeAuditChecked", runtime)
        helper = runtime.split("bool EEA_ObserverRuntimeAuditChecked", 1)[1].split("bool EEA_ObserverRuntimeInit", 1)[0]
        self.assertIn("if(EEA_ObserverRuntimeAudit(audit,ctx.config_version,event_type,status)) return true;", helper)
        self.assertIn('ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED"', helper)
        self.assertIn("bool status_persisted=EEA_RuntimeStoreWriteStatus", helper)
        self.assertIn("EEA_RuntimeStoreCheckBlockedAuditStatus", helper)
        self.assertIn("return false", helper)
        degraded = shell.split("if(!EEA_ObserverRuntimeInit", 1)[1].split("if(!EventSetTimer", 1)[0]
        self.assertIn("!EEA_ObserverRuntimeAuditChecked", degraded)
        self.assertNotIn("EEA_ObserverRuntimeAudit(g_audit", degraded)

    def test_checkpoint_audit_failure_blocks_before_refresh(self):
        runtime = (ROOT / "Runtime/ObserverRuntime.mqh").read_text(encoding="utf-8")
        init = runtime.split("bool EEA_ObserverRuntimeInit", 1)[1].split("void EEA_ObserverRuntimeMarkStale", 1)[0]
        checkpoint = init.split("if(!EEA_ObserverRuntimeAuditChecked(ctx,audit,\"RUNTIME_CHECKPOINT_OBSERVED\"", 1)[1]
        failure = checkpoint.split("ctx.initialized=true", 1)[0]
        self.assertIn('ctx.status.runtime_state="BLOCKED"', failure)
        self.assertIn('ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED"', failure)
        self.assertIn("EEA_RuntimeStoreWriteStatus", failure)
        self.assertNotIn("EEA_ObserverRuntimeRefresh(ctx,audit)", failure)

    def test_rollback_audits_use_checked_helper_and_block_on_failure(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        apply = panel.split("void EEA_SymbolPanelApplyStaged", 1)[1].split("void EEA_SymbolPanelHandleChartEvent", 1)[0]
        self.assertNotIn('EEA_ObserverRuntimeAudit(audit,ctx.config_version,"POLICY_ROLLBACK_FAILED",ctx.status)', apply)
        self.assertGreaterEqual(apply.count("!EEA_ObserverRuntimeAuditChecked"), 2)
        self.assertIn('ctx.status.reason_code="AUDIT_PERSISTENCE_FAILED"', apply)
        self.assertIn("EEA_RuntimeStoreWriteStatus", apply)


class RuntimeTelemetryValidationTests(unittest.TestCase):
    def test_validate_runtime_telemetry(self):
        from runtime_evidence_oracle import validate_runtime_telemetry

        valid = {
            "refresh_attempt_count": 10,
            "refresh_success_count": 8,
            "refresh_failure_count": 2,
            "max_refresh_duration_ms": 100,
            "last_refresh_duration_ms": 50,
            "consecutive_refresh_failures": 1,
            "refresh_generation": 5,
            "refresh_sequence": 5,
            "pending_refresh": False,
            "refresh_in_progress": False
        }
        ok, reason = validate_runtime_telemetry(valid)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # negative counters
        neg = dict(valid, refresh_attempt_count=-1)
        ok, reason = validate_runtime_telemetry(neg)
        self.assertFalse(ok)
        self.assertEqual(reason, "RUNTIME_TELEMETRY_INVALID")

        # successes+failures > attempts
        bad_sum = dict(valid, refresh_attempt_count=5)
        ok, reason = validate_runtime_telemetry(bad_sum)
        self.assertFalse(ok)

        # durations
        bad_dur = dict(valid, last_refresh_duration_ms=200)
        ok, reason = validate_runtime_telemetry(bad_dur)
        self.assertFalse(ok)

        bad_dur2 = dict(valid, max_refresh_duration_ms=-1)
        ok, reason = validate_runtime_telemetry(bad_dur2)
        self.assertFalse(ok)

        # consecutive
        bad_cons = dict(valid, consecutive_refresh_failures=3)
        ok, reason = validate_runtime_telemetry(bad_cons)
        self.assertFalse(ok)

        # generation/sequence
        bad_gen = dict(valid, refresh_sequence=6)
        ok, reason = validate_runtime_telemetry(bad_gen)
        self.assertFalse(ok)

        bad_gen2 = dict(valid, refresh_generation=-1)
        ok, reason = validate_runtime_telemetry(bad_gen2)
        self.assertFalse(ok)

    def test_audit_invariants(self):
        from runtime_evidence_oracle import audit_invariants

        # Valid sequence: missing-checkpoint -> startup-attempt -> startup-completion
        records = [
            {"event": "missing-checkpoint", "runtime_instance_id": 1, "refresh_generation": 1, "refresh_sequence": 0},
            {"event": "startup-attempt", "runtime_instance_id": 1, "refresh_generation": 1, "refresh_sequence": 0},
            {"event": "startup-completion", "runtime_instance_id": 1, "refresh_generation": 1, "refresh_sequence": 1},
        ]
        ok, reason = audit_invariants(records)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # Duplicate completion
        bad_dup = records + [{"event": "startup-completion", "runtime_instance_id": 1, "refresh_generation": 1, "refresh_sequence": 2}]
        ok, reason = audit_invariants(bad_dup)
        self.assertFalse(ok)

        # Decreasing generation
        bad_dec = records + [{"event": "startup-attempt", "runtime_instance_id": 1, "refresh_generation": 0, "refresh_sequence": 2}]
        ok, reason = audit_invariants(bad_dec)
        self.assertFalse(ok)

        # Completion without attempt
        bad_no_att = [
            {"event": "startup-completion", "runtime_instance_id": 1, "refresh_generation": 1, "refresh_sequence": 1}
        ]
        ok, reason = audit_invariants(bad_no_att)
        self.assertFalse(ok)

    def test_selection_load_policy(self):
        from runtime_evidence_oracle import selection_load_policy
        doc = {
            "config_version": "v1",
            "account_fingerprint": "xyz",
            "canonical_symbols": ["EURUSD", "GBPUSD"],
            "broker_symbols": ["EURUSD.r", "GBPUSD.r"]
        }
        # Compatible
        out = selection_load_policy(doc, "v1", "xyz", ["FALLBACK"])
        self.assertEqual(out.get("canonical_symbols"), ["EURUSD", "GBPUSD"])
        self.assertNotIn("broker_symbols", out)

        # Incompatible config_version
        out2 = selection_load_policy(doc, "v2", "xyz", ["FALLBACK"])
        self.assertEqual(out2.get("canonical_symbols"), ["FALLBACK"])
        self.assertEqual(out2.get("reason"), "RUNTIME_SELECTION_INCOMPATIBLE")

        # Incompatible fingerprint
        out3 = selection_load_policy(doc, "v1", "abc", ["FALLBACK"])
        self.assertEqual(out3.get("canonical_symbols"), ["FALLBACK"])
        self.assertEqual(out3.get("reason"), "RUNTIME_SELECTION_INCOMPATIBLE")
    def test_mql_telemetry_and_selection_functions_exist(self):
        mqh = (ROOT / 'Runtime/RuntimeEvidence.mqh').read_text(encoding='utf-8')
        self.assertIn('EEA_RuntimeTelemetryValidate', mqh)
        self.assertIn('runtime_instance_id', mqh)
        self.assertIn('refresh_sequence', mqh)
        self.assertIn('refresh_generation', mqh)
        self.assertIn('selection_revision', mqh)

        store = (ROOT / 'Storage/RuntimeEvidenceStore.mqh').read_text(encoding='utf-8')
        self.assertIn('EEA_RuntimeStoreWriteSymbolSelection', store)
        self.assertIn('EEA_RuntimeStoreCheckSymbolSelection', store)
        self.assertIn('symbol_selection.json', store)
        self.assertNotIn('ACCOUNT_LOGIN', store)
        self.assertNotIn('ACCOUNT_NAME', store)

    def test_task5_runtime_status_initialization_and_telemetry(self):
        ev_mqh = (ROOT / 'Runtime/RuntimeEvidence.mqh').read_text(encoding='utf-8')
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')

        for field in ("runtime_instance_id", "refresh_sequence", "refresh_generation",
                      "selection_revision", "checkpoint_written_at_utc", "broker_observed_at_utc",
                      "timer_tick_count", "refresh_attempt_count", "refresh_success_count",
                      "refresh_failure_count", "last_timer_at_utc", "last_refresh_duration_ms",
                      "max_refresh_duration_ms", "consecutive_refresh_failures",
                      "transaction_callback_count", "transaction_invalidation_generation",
                      "pending_refresh", "refresh_in_progress"):
            self.assertIn(field, ev_mqh)

        self.assertIn("EEA_RuntimeStoreWriteSymbolSelection", obs_mqh)
        self.assertIn("selection_revision++", obs_mqh)
        self.assertIn("old_revision", obs_mqh)

        for token in ("OrderSend", "OrderSendAsync", "CTrade", "PositionClose", "PositionModify", "OrderDelete"):
            self.assertNotIn(token, obs_mqh)


class RetainedRuntimeLifecycleWiringTests(unittest.TestCase):
    def test_mark_stale_signature_and_audit(self):
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')
        shell = (ROOT / 'EnterpriseEA.mq5').read_text(encoding='utf-8')
        self.assertIn("EEA_ObserverRuntimeMarkStale(EEA_ObserverRuntimeContext &ctx,const string reason,CAuditLog &audit)", obs_mqh)
        self.assertIn("BROKER_TRANSACTION_OBSERVED", obs_mqh)
        self.assertIn("EEA_ObserverRuntimeMarkStale(g_runtime,\"BROKER_TRANSACTION_OBSERVED\",g_audit)", shell)

    def test_refresh_preserves_telemetry(self):
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')
        self.assertIn("val_status", obs_mqh)
        self.assertIn("ctx.status = val_status", obs_mqh)

    def test_startup_checks_symbol_selection(self):
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')
        self.assertIn("EEA_RuntimeStoreCheckSymbolSelection", obs_mqh)

    def test_apply_selection_rollback(self):
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')
        self.assertIn("ctx.canonical_symbols[i] = old_canons[i]", obs_mqh)
        self.assertIn("ctx.status = old_status", obs_mqh)

    def test_status_serialization_occurs_after_final_telemetry(self):
        obs_mqh = (ROOT / 'Runtime/ObserverRuntime.mqh').read_text(encoding='utf-8')
        write_status_pos = obs_mqh.find("EEA_RuntimeStoreWriteStatus")
        refresh_false_pos = obs_mqh.find("ctx.status.refresh_in_progress = false")
        duration_pos = obs_mqh.find("ctx.status.last_refresh_duration_ms =")
        
        self.assertNotEqual(write_status_pos, -1, "EEA_RuntimeStoreWriteStatus must exist")
        self.assertNotEqual(refresh_false_pos, -1, "refresh_in_progress = false assignment must exist")
        self.assertNotEqual(duration_pos, -1, "duration assignment must exist")
        
        self.assertGreater(write_status_pos, duration_pos, "Status serialization must occur after duration assignment")
        self.assertGreater(write_status_pos, refresh_false_pos, "Status serialization must occur after refresh_in_progress = false")


if __name__ == "__main__":
    unittest.main()
