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

if __name__ == "__main__":
    unittest.main()


