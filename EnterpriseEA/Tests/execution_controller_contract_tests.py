"""Static contract checks for the fail-closed execution controller state."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "Runtime" / "ExecutionControllerState.mqh"


class ExecutionControllerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = CONTRACT.read_text(encoding="utf-8") if CONTRACT.exists() else ""

    def _section(self, signature, next_signature=None):
        self.assertIn(signature, self.source)
        start = self.source.index(signature)
        if next_signature is None:
            return self.source[start:]
        self.assertIn(next_signature, self.source[start:])
        end = self.source.index(next_signature, start)
        return self.source[start:end]

    def test_contract_declares_fail_closed_operator_scoped_state(self):
        self.assertTrue(CONTRACT.exists())
        for declaration in (
            "struct EEA_ExecutionControllerState",
            "bool kill_active",
            "long revision",
            "string operator_id",
            "string reference",
            "datetime valid_from_utc",
            "datetime valid_until_utc",
            "string operation_scope",
        ):
            self.assertIn(declaration, self.source)

    def test_defaults_keep_kill_switch_active_and_metadata_empty(self):
        defaults = self._section(
            "void EEA_ExecutionControllerStateDefaults",
            "bool EEA_ExecutionControllerStateValid",
        )
        self.assertIn("state.kill_active=true;", defaults)
        self.assertIn("state.revision=0;", defaults)
        self.assertIn('state.operator_id="";', defaults)
        self.assertIn('state.reference="";', defaults)
        self.assertIn("state.valid_from_utc=0;", defaults)
        self.assertIn("state.valid_until_utc=0;", defaults)
        self.assertIn('state.operation_scope="";', defaults)

    def test_validation_requires_identity_revision_scope_and_valid_window(self):
        validation = self._section(
            "bool EEA_ExecutionControllerStateValid",
            "bool EEA_ExecutionControllerAllowsNewRequest",
        )
        for required_check in (
            "now_utc<=0",
            "state.revision<=0",
            'state.operator_id==""',
            'state.reference==""',
            "state.valid_from_utc<=0",
            "state.valid_until_utc<=state.valid_from_utc",
            "now_utc<state.valid_from_utc",
            "now_utc>=state.valid_until_utc",
            'state.operation_scope==""',
        ):
            self.assertIn(required_check, validation)

    def test_new_request_helper_is_fail_closed_and_exactly_scoped(self):
        helper = self._section("bool EEA_ExecutionControllerAllowsNewRequest")
        self.assertIn("state.kill_active", helper)
        self.assertIn("!EEA_ExecutionControllerStateValid(state,now_utc)", helper)
        self.assertIn('requested_scope==""', helper)
        self.assertIn("requested_scope!=state.operation_scope", helper)

    def test_contract_has_no_broker_io_or_live_path_dependencies(self):
        forbidden = (
            "#include",
            "OrderSend",
            "CTrade",
            "FileOpen",
            "WebRequest",
            "SymbolInfo",
            "AccountInfo",
            "PositionGet",
            "ExecutionAdapter",
            "ExecutionGate",
            "EnterpriseEA.mq5",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
