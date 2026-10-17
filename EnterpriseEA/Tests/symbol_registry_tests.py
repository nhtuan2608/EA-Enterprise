"""Synthetic tests for explicit canonical-to-broker symbol resolution."""
import json
import unittest
from pathlib import Path

from symbol_registry_oracle import resolve, suggest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/symbol-resolution-v0.1.0.json").read_text(encoding="utf-8"))


class SymbolRegistryExamples(unittest.TestCase):
    def test_batch_resolution_and_ranking(self):
        available = [
            {"name": "EURUSD", "tradeable": False, "conversion_only": False},
            {"name": "EURUSD-VIP", "tradeable": True, "conversion_only": False},
            {"name": "mEURUSD", "tradeable": True, "conversion_only": False},
            {"name": "XAUUSD.crp", "tradeable": False, "conversion_only": True},
            {"name": "XAUUSD-VIP", "tradeable": True, "conversion_only": False},
            {"name": "USDX.", "tradeable": True, "conversion_only": False},
        ]
        from symbol_registry_oracle import resolve_batch
        rows = resolve_batch(["EURUSD", "XAUUSD", "DXY"], available)
        self.assertEqual([row["canonical_symbol"] for row in rows], ["EURUSD", "XAUUSD", "DXY"])
        self.assertEqual(rows[0]["status"], "AMBIGUOUS")
        self.assertEqual(rows[1]["broker_symbol"], "XAUUSD-VIP")
        self.assertEqual(rows[2]["broker_symbol"], "USDX.")
        self.assertEqual(rows[2]["reason_code"], "UNIQUE_ALIAS_ROOT_MATCH")
    def test_broker_aliases_for_wti_and_sp500(self):
        # Lirunex (17/10/2026) names WTI crude USOIL.r and the S&P 500 SPCUSD.r; its swap-free twins start with "s".
        from symbol_registry_oracle import resolve_batch
        available = [{"name": n, "tradeable": True, "conversion_only": False}
                     for n in ("USOIL.r", "sUSOIL.r", "SPCUSD.r", "XAUUSD.r", "sXAUUSD.r")]
        rows = resolve_batch(["USOUSD", "US500", "XAUUSD", "ETHUSD"], available)
        self.assertEqual([r["broker_symbol"] for r in rows[:3]], ["USOIL.r", "SPCUSD.r", "XAUUSD.r"])
        self.assertEqual(rows[0]["reason_code"], "UNIQUE_ALIAS_ROOT_MATCH")
        self.assertEqual(rows[3]["status"], "MISSING")                     # no ETH on this broker: stays unresolved
        source = (ROOT / "Market/SymbolRegistry.mqh").read_text(encoding="utf-8")
        for alias in ('"USDX"', '"USOIL"', '"XTIUSD"', '"WTI"', '"SPCUSD"', '"SPX500"', '"SP500"', '"USA500"'):
            self.assertIn(alias, source)
        self.assertIn("for(int a = 0; a < alias_count; a++)", source)

    def test_explicit_resolution_and_fail_closed_cases(self):
        for row in FIXTURE["cases"]:
            with self.subTest(name=row["name"]):
                runtime = dict(FIXTURE["runtime_template"])
                runtime.update(row.get("runtime", {}))
                actual = resolve("EURUSD", row["entries"], runtime)
                for key, expected in row["expected"].items():
                    self.assertEqual(actual[key], expected)

    def test_prefix_suffix_suggestions_never_resolve_mapping(self):
        for row in FIXTURE["suggestion_cases"]:
            with self.subTest(available=row["available"]):
                count, candidate = suggest(row["canonical"], row["available"])
                self.assertEqual(count, row["expected_count"])
                self.assertEqual(candidate, row["expected_suggestion"])
                runtime = dict(FIXTURE["runtime_template"])
                unresolved = resolve(row["canonical"], [], runtime)
                self.assertEqual(unresolved["resolved"], row["expected_resolved"])
                self.assertEqual(unresolved["status"], "UNRESOLVED")

    def test_resolver_is_pure_and_not_included_by_shell(self):
        source = (ROOT / "Market/SymbolRegistry.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_ResolveSymbol", source)
        self.assertIn("EEA_SuggestBrokerSymbol", source)
        self.assertNotIn("SymbolInfo", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("SymbolRegistry.mqh", shell)
        self.assertIn("EEA_SymbolDiscoveryCandidate", source)
        self.assertIn("EEA_SymbolDiscoveryResult", source)
        self.assertIn("EEA_NormalizeCanonicalCsv", source)
        self.assertIn("EEA_RankSymbolCandidate", source)
        self.assertIn("EEA_ResolveSymbolsBatch", source)
        self.assertNotIn("return 0; // Stub", source)


if __name__ == "__main__":
    unittest.main()

