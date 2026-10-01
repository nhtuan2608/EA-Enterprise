"""Static integration checks for the reachable, disabled-by-default execution boundary."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExecutionIntegrationBoundaryTests(unittest.TestCase):
    def test_shell_includes_adapter_for_compilation(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn('#include "Runtime/ExecutionAdapter.mqh"', shell)

    def test_shell_has_no_automatic_execution_invocation(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for symbol in (
            "EEA_ExecutionSubmit(",
            "EEA_ExecutionModifyProtective(",
            "EEA_ExecutionCancelPending(",
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
        ):
            start = adapter.index("bool " + function_name)
            end = adapter.find("\nbool ", start + 1)
            section = adapter[start:] if end < 0 else adapter[start:end]
            self.assertIn("const EEA_LiveAuthorizationDecision &authorization", section)
            self.assertIn("EEA_ExecutionAuthorizationBinds(authorization,intent,account,symbol)", section)
        self.assertIn('authorization.authorized && authorization.status=="AUTHORIZED_CONTROLLED_LIVE"', adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_SUBMIT_MARKET", adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_SUBMIT_PENDING", adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_MODIFY_PROTECTIVE", adapter)
        self.assertIn("intent.action!=EEA_EXEC_ACTION_CANCEL_PENDING", adapter)

    def test_pending_protective_modify_uses_modify_action(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("request.action = TRADE_ACTION_MODIFY;", adapter)
        self.assertIn("request.action = TRADE_ACTION_SLTP;", adapter)
        self.assertIn("if(intent.position_ticket > 0)", adapter)
        self.assertIn("request.order = (ulong)intent.ticket;", adapter)

    def test_mql_gate_matches_runtime_state_and_symbol_metadata(self):
        gate = (ROOT / "Runtime/ExecutionGate.mqh").read_text(encoding="utf-8")
        evidence = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        self.assertIn('status.runtime_state!="OBSERVING"', gate)
        self.assertIn("status.new_entries_blocked", gate)
        self.assertIn("symbol.metadata_fingerprint", gate)
        self.assertIn('"SYMBOL_FINGERPRINT_MISMATCH"', gate)
        self.assertIn("metadata_fingerprint", evidence)

    def test_ack_and_persistence_failures_are_operation_specific(self):
        adapter = (ROOT / "Runtime/ExecutionAdapter.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_ExecutionRetcodeAcknowledged(trade_result.retcode,intent.action)", adapter)
        self.assertIn("EEA_ExecutionPersistAfterSend", adapter)
        self.assertIn("if(!result_written || !audit_written)", adapter)
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

    def test_symbol_metadata_fingerprint_is_derived_and_persisted(self):
        symbol_adapter = (ROOT / "Runtime/SymbolSpecAdapter.mqh").read_text(encoding="utf-8")
        evidence = (ROOT / "Runtime/RuntimeEvidence.mqh").read_text(encoding="utf-8")
        store = (ROOT / "Storage/RuntimeEvidenceStore.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_RuntimeSymbolFingerprint", evidence)
        self.assertIn("EEA_RuntimeSymbolFingerprint(spec)", symbol_adapter)
        self.assertIn("metadata_fingerprint", store)


if __name__ == "__main__":
    unittest.main()
