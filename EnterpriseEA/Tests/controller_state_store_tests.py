"""Focused storage-contract checks for the durable fail-closed controller state."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "Storage" / "ControllerStateStore.mqh"
CONTRACT = ROOT / "Runtime" / "ExecutionControllerState.mqh"


class ControllerStateStoreTests(unittest.TestCase):
    def test_shell_loads_durable_controller_after_runtime_identity_is_available(self):
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn('#include "Storage/ControllerStateStore.mqh"', shell)
        self.assertIn("EEA_ControllerStateStoreLoad", shell)
        self.assertIn('"MARKET_ENTRY"', shell)
        self.assertIn("EEA_LoadDurableControllerState", shell)

    @classmethod
    def setUpClass(cls):
        cls.store = STORE.read_text(encoding="utf-8") if STORE.exists() else ""
        cls.contract = CONTRACT.read_text(encoding="utf-8") if CONTRACT.exists() else ""

    def _section(self, signature, next_signature=None):
        self.assertIn(signature, self.store)
        start = self.store.index(signature)
        if next_signature is None:
            return self.store[start:]
        self.assertIn(next_signature, self.store[start:])
        return self.store[start:self.store.index(next_signature, start)]

    def test_write_uses_versioned_redacted_atomic_document(self):
        self.assertTrue(STORE.exists())
        write = self._section(
            "bool EEA_ControllerStateStoreWrite",
            "EEA_ControllerStateLoadStatus EEA_ControllerStateStoreLoad",
        )
        self.assertIn('"controller-state-v0.1.0"', self.store)
        self.assertIn('"execution-controller-state-v1.0.0"', self.store)
        self.assertIn("EEA_WriteAtomicText(path,json)", write)
        for field in (
            "config_version",
            "account_fingerprint",
            "broker_server",
            "revision",
            "kill_active",
            "operator_id",
            "reference",
            "valid_from_utc",
            "valid_until_utc",
            "operation_scope",
        ):
            self.assertIn(field, self.store)
        for forbidden in ("ACCOUNT_LOGIN", "ACCOUNT_NAME", "password", "secret", "credential"):
            self.assertNotIn(forbidden, self.store)
        for forbidden in ("OrderSend", "CTrade", "PositionOpen", "PositionClose"):
            self.assertNotIn(forbidden, self.store)

    def test_load_defaults_kill_active_for_missing_or_corrupt_document(self):
        load = self._section("EEA_ControllerStateLoadStatus EEA_ControllerStateStoreLoad")
        self.assertIn("EEA_ExecutionControllerStateDefaults(state)", load)
        self.assertIn("EEA_CONTROLLER_STATE_MISSING", load)
        self.assertIn("EEA_CONTROLLER_STATE_CORRUPT", load)
        self.assertIn("EEA_ControllerStateStoreParseDocument", load)
        self.assertIn("return EEA_CONTROLLER_STATE_CORRUPT", load)

    def test_load_enforces_exact_identity_scope_window_and_minimum_revision(self):
        load = self._section("EEA_ControllerStateLoadStatus EEA_ControllerStateStoreLoad")
        for required_check in (
            "config_version!=expected_config_version",
            "account_fingerprint!=expected_account_fingerprint",
            "broker_server!=expected_broker_server",
            "state.operation_scope!=expected_scope",
            "state.revision<minimum_revision",
            "!EEA_ExecutionControllerStateValid(state,now_utc)",
        ):
            self.assertIn(required_check, load)
        self.assertIn("EEA_CONTROLLER_STATE_IDENTITY_MISMATCH", load)
        self.assertIn("EEA_CONTROLLER_STATE_SCOPE_MISMATCH", load)
        self.assertIn("EEA_CONTROLLER_STATE_REVISION_ROLLBACK", load)
        self.assertIn("EEA_CONTROLLER_STATE_STALE", load)
        parser = self._section(
            "bool EEA_ControllerStateStoreParseDocument",
            "bool EEA_ControllerStateStoreReadExisting",
        )
        self.assertIn("cursor!=StringLen(json)", parser)
        self.assertIn('"schema_version"', parser)
        self.assertIn('"document_version"', parser)

    def test_write_rejects_non_monotonic_revision_against_existing_state(self):
        write = self._section(
            "bool EEA_ControllerStateStoreWrite",
            "EEA_ControllerStateLoadStatus EEA_ControllerStateStoreLoad",
        )
        self.assertIn("EEA_ControllerStateStoreReadExisting", write)
        self.assertIn("state.revision<=existing.revision", write)
        self.assertIn("EEA_ExecutionControllerStateValid(state,now_utc)", write)

    def test_runtime_contract_binds_state_to_config_and_account_identity(self):
        for declaration in (
            "string config_version",
            "string account_fingerprint",
            "string broker_server",
        ):
            self.assertIn(declaration, self.contract)
        defaults = self.contract[self.contract.index("void EEA_ExecutionControllerStateDefaults"):]
        self.assertIn('state.config_version="";', defaults)
        self.assertIn('state.account_fingerprint="";', defaults)
        self.assertIn('state.broker_server="";', defaults)


if __name__ == "__main__":
    unittest.main(verbosity=2)
