"""Static integration checks for the reachable, disabled-by-default execution boundary."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExecutionIntegrationBoundaryTests(unittest.TestCase):
    def test_shell_includes_adapter_for_compilation(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn('#include "Runtime/ExecutionAdapter.mqh"', shell)
        self.assertIn('#include "Runtime/ExecutionControllerState.mqh"', shell)
        self.assertIn('#include "Risk/RiskDecision.mqh"', shell)

    def test_shell_has_no_automatic_execution_invocation(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for symbol in (
            "EEA_ExecutionSubmit(",
            "EEA_ExecutionModifyProtective(",
            "EEA_ExecutionCancelPending(",
            "EEA_ExecutionClosePosition(",
        ):
            self.assertNotIn(symbol, shell)

    def test_adapter_uses_mql5_filling_enum_without_implicit_char_cast(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("ENUM_ORDER_TYPE_FILLING", adapter)
        self.assertNotIn("ENUM_ORDER_FILLING", adapter)
        self.assertNotIn("+ '\"'", adapter)
        self.assertIn("(long)trade_result.deal", adapter)
        self.assertIn("(long)trade_result.order", adapter)

    def test_every_send_path_requires_live_authorization_and_exact_action(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn('#include "LiveAuthorizationGate.mqh"', adapter)
        for function_name in (
            "EEA_ExecutionSubmit",
            "EEA_ExecutionModifyProtective",
            "EEA_ExecutionCancelPending",
            "EEA_ExecutionClosePosition",
        ):
            start = adapter.index("bool " + function_name)
            end = adapter.find("\nbool ", start + 1)
            section = adapter[start:] if end < 0 else adapter[start:end]
            self.assertIn("const EEA_LiveAuthorizationDecision &authorization", section)
            self.assertIn("EEA_ExecutionAuthorizationBinds(authorization,intent,account,symbol)", section)
        self.assertIn('authorization.authorized && authorization.status=="AUTHORIZED_CONTROLLED_LIVE"', adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_SUBMIT_MARKET", adapter)
        self.assertIn("intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING", adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_MODIFY_PROTECTIVE", adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_CANCEL_PENDING", adapter)

    def test_market_submit_requires_durable_controller_scope(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn('#include "ExecutionControllerState.mqh"', adapter)
        submit = adapter.split("bool EEA_ExecutionSubmit", 1)[1].split("\nbool ", 1)[0]
        self.assertIn("const EEA_ExecutionControllerState &controller", submit)
        self.assertIn("requested_scope", submit)
        self.assertIn("EEA_ExecutionControllerAllowsNewRequest", submit)
        self.assertIn("CONTROLLER_SCOPE_REJECTED", submit)

    def test_pending_protective_modify_uses_modify_action(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("request.action = TRADE_ACTION_MODIFY;", adapter)
        self.assertIn("request.action = TRADE_ACTION_SLTP;", adapter)
        self.assertIn("if(intent.position_ticket > 0)", adapter)
        self.assertIn("request.order = (ulong)intent.ticket;", adapter)

    def test_pending_runtime_scope_is_explicit_and_stop_limit_stays_out(self):
        gate_text = (ROOT / "Runtime/ExecutionGate.mqh").read_text(encoding="utf-8")
        adapter_text = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        for token in ('"PENDING_ORDER_TYPE_UNSUPPORTED"', '"PENDING_EXPIRATION_UNSUPPORTED"', "SYMBOL_EXPIRATION_SPECIFIED"):
            self.assertIn(token, gate_text)
        self.assertIn('requested_scope!="PENDING_ENTRY"', adapter_text)
        self.assertIn("request.type_time = ORDER_TIME_SPECIFIED;", adapter_text)
        self.assertNotIn("ORDER_TIME_GTC", adapter_text)
        self.assertIn('"PENDING_PRICE_GEOMETRY_INVALID"', adapter_text)
        self.assertIn('"PENDING_ORDER_NOT_ACTIVE_OR_NOT_OWNED"', adapter_text)
        self.test_modify_without_position_is_still_denied()

    def test_modify_without_position_is_still_denied(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        gate = (ROOT / "Runtime/ExecutionGate.mqh").read_text(encoding="utf-8")
        self.assertIn('"PENDING_RUNTIME_NOT_IMPLEMENTED"', adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_SUBMIT_MARKET", adapter)
        self.assertIn("intent.position_ticket<=0", adapter)
        self.assertIn('"PENDING_RUNTIME_NOT_IMPLEMENTED"', gate)
        self.assertIn("intent.action==EEA_EXEC_ACTION_SUBMIT_PENDING", gate)
        self.assertIn("intent.action==EEA_EXEC_ACTION_CANCEL_PENDING", gate)
        self.assertIn("intent.order_type>1", gate)

    def test_mql_gate_matches_runtime_state_and_symbol_metadata(self):
        gate = (ROOT / "Runtime/ExecutionGate.mqh").read_text(encoding="utf-8")
        evidence = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        self.assertIn('status.runtime_state!="OBSERVING"', gate)
        self.assertIn("status.new_entries_blocked", gate)
        self.assertIn("symbol.metadata_fingerprint", gate)
        self.assertIn('"SYMBOL_FINGERPRINT_MISMATCH"', gate)
        self.assertIn("metadata_fingerprint", evidence)
        self.assertIn("ACCOUNT_FINANCIAL_STATE_INVALID", gate)

    def test_ack_and_persistence_failures_are_operation_specific(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_ExecutionRetcodeAcknowledged(trade_result.retcode,intent.action)", adapter)
        self.assertIn("EEA_ExecutionPersistAfterSend", adapter)
        self.assertIn("if(!audit_written)", adapter)
        self.assertIn("EEA_ExecutionStoreWriteResult(root,result);", adapter)
        self.assertIn("EEA_JsonEscape(idempotency_key)", adapter)
        self.assertIn("if(action==EEA_EXEC_ACTION_CANCEL_PENDING)\n      return retcode==TRADE_RETCODE_DONE;", adapter)
        self.assertIn("bool marker_written=EEA_WriteAtomicText", adapter)

    def test_authorization_is_bound_and_records_are_replayable(self):
        auth = (ROOT / "Runtime/LiveAuthorizationGate.mqh").read_text(encoding="utf-8")
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        self.assertIn("account_fingerprint", auth)
        self.assertIn("intent_id", auth)
        self.assertIn("authorization_valid_until_utc", auth)
        self.assertIn("EEA_ExecutionAuthorizationBinds", adapter)
        for field in ("action", "order_type", "volume", "price", "sl", "tp", "ticket", "position_ticket", "magic", "filling_mode"):
            self.assertIn("intent." + field, store)
        self.assertIn("execution_persistence_failure.json", adapter)

    def test_execution_intent_requires_risk_and_strategy_lineage(self):
        contracts = (ROOT / "Runtime/ExecutionContracts.mqh").read_text(encoding="utf-8")
        gate = (ROOT / "Runtime/ExecutionGate.mqh").read_text(encoding="utf-8")
        binding = (ROOT / "Runtime/RiskDecisionBinding.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        for field in (
            "candidate_id", "setup_id", "setup_version", "risk_decision_id",
            "risk_decision_status", "risk_policy_snapshot_id", "portfolio_snapshot_id",
            "quote_snapshot_id", "reconciliation_snapshot_id", "entry_reference",
            "risk_budget", "projected_loss", "net_reward_risk",
        ):
            self.assertIn(field, contracts)
            self.assertIn("intent." + field, store)
        self.assertIn('intent.risk_decision_status!="RISK_APPROVED"', gate)
        self.assertIn('"RISK_DECISION_LINEAGE_MISSING"', gate)
        self.assertIn("EEA_RiskDecisionBindsExecutionIntent", binding)
        self.assertIn("EEA_RiskDecisionValidForRelease", binding)
        self.assertIn("EEA_ExecutionGateCheckReleased", gate)
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("const EEA_RiskDecision &decision", adapter)
        self.assertIn("EEA_ExecutionGateCheckReleased", adapter)

    def test_symbol_metadata_fingerprint_is_derived_and_persisted(self):
        symbol_adapter = (ROOT / "Runtime/SymbolSpecAdapter.mqh").read_text(encoding="utf-8")
        evidence = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_RuntimeSymbolFingerprint", evidence)
        self.assertIn("EEA_RuntimeSymbolFingerprint(spec)", symbol_adapter)
        self.assertIn("metadata_fingerprint", store)


    def test_entry_type_is_selected_automatically(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        live = (ROOT / "Integration/ControlledLiveRuntime.mqh").read_text(encoding="utf-8")
        self.assertNotIn("InpS02EntryMode", shell)
        self.assertNotIn("config.entry_mode", live)
        selector = live.split("int EEA_S02SelectEntryMode", 1)[1].split("\n  }\n", 1)[0]
        for token in ("EEA_S02_ENTRY_LIMIT_AT_ZONE", "EEA_S02_ENTRY_MARKET",
                      "EEA_S02_ENTRY_STOP_ABOVE_TRIGGER", "ENTRY_AUTO_CHASE_TOO_FAR",
                      "ENTRY_AUTO_WAIT_TRIGGER_COUNTER_HTF", "htf_risk_modifier"):
            self.assertIn(token, selector)
        on_timer = live.split("bool EEA_ControlledLiveOnTimer", 1)[1]
        self.assertIn("EEA_S02SelectEntryMode(strategy,i,", on_timer)
        self.assertIn("CONTROLLED_LIVE_SCOPE_NOT_GRANTED_", on_timer)
        # The chosen scope still goes through the controller on submit.
        self.assertIn("EEA_ExecutionSubmit(audit,observer.root,intent,decision,controller,scope,", on_timer)
        self.assertIn("entry_selection", live)


if __name__ == "__main__":
    unittest.main()
