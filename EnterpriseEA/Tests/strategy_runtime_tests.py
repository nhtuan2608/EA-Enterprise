import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StrategyRuntimeTests(unittest.TestCase):
    def test_closed_bar_runtime_is_explicitly_disabled_and_no_trade_api(self):
        source = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for token in (
            "EEA_StrategyCandidateRuntime",
            "EEA_StrategyRuntimeOnTimer",
            "CopyRates",
            "iATR",
            "IndicatorRelease",
            "PERIOD_M5",
            "EEA_S02ProcessClosedBar",
            "EEA_STRATEGY_RUNTIME_DISABLED",
            "MQL_TESTER",
        ):
            self.assertIn(token, source if token != "MQL_TESTER" else shell)
        self.assertIn("InpStrategyRuntimeEnabled=false", shell)
        self.assertIn('StrategyCandidateRuntime.mqh', shell)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("FileOpen", source)

    def test_runtime_uses_completed_series_index_one_and_pins_candidate_level(self):
        source = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")
        self.assertIn("CopyRates(broker_symbol,PERIOD_M5,1", source)
        self.assertIn("engine.key_level", source)
        self.assertIn("candidate.state", source)
        self.assertIn("EEA_S02IsTerminal", source)


if __name__ == "__main__":
    unittest.main()
