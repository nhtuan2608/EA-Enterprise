import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StrategyCandidateStoreTests(unittest.TestCase):
    def test_store_is_atomic_identity_bound_and_not_a_trade_ledger(self):
        source = (ROOT / "Storage/StrategyCandidateStore.mqh").read_text(encoding="utf-8")
        for token in (
            "EEA_StrategyCandidateStoreWrite",
            "EEA_StrategyCandidateStoreLoad",
            "EEA_WriteAtomicText",
            "account_fingerprint",
            "broker_server",
            "config_version",
            "last_processed_bar_utc",
            "CANDIDATE_CHECKPOINT_STALE",
        ):
            self.assertIn(token, source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("Paper", source)
        self.assertNotIn("ledger", source.lower())

    def test_runtime_wires_checkpoint_load_and_write(self):
        runtime = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_StrategyCandidateStoreLoad", runtime)
        self.assertIn("EEA_StrategyCandidateStoreWrite", runtime)
        self.assertIn("EEA_StrategyRuntimeLoadCheckpoints", runtime)
        self.assertIn("EEA_StrategyRuntimeWriteCheckpoints", runtime)
        self.assertIn("StrategyCandidateStore.mqh", runtime)
        self.assertIn("EEA_StrategyRuntimeLoadCheckpoints", shell)


if __name__ == "__main__":
    unittest.main()
