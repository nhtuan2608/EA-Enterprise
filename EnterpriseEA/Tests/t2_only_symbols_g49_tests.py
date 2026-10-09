"""G49: the G41 trend assets (XAGUSD, ETHUSD, USOUSD) run T2 alone (InpT2OnlySymbols); every other setup
keeps to InpCanonicalSymbols, and T2 LIVE keeps to InpT2LiveSymbols (XAUUSD, BTCUSD)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


def slots(s04=True, s06=False, s06b=True, t2=True):
    """Mirror of EEA_StrategyRuntimeStride / EEA_StrategyRuntimeSlot: the setup of each slot of a symbol."""
    out = ["S02", "S02"] + (["S04", "S04"] if s04 else []) + (["S06"] if s06 else []) + (["S06B"] if s06b else [])
    return out + (["T2"] if t2 else [])


def engines(symbols, t2_only, **modes):
    """Mirror of EEA_StrategyCandidateRuntimeInitV1 with EEA_StrategyRuntimeSlotFor."""
    return [(s, setup) for s in symbols for setup in slots(**modes) if s not in t2_only or setup == "T2"]


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_inputs(self):
        self.assertIn('input string InpT2OnlySymbols           = "XAGUSD,ETHUSD,USOUSD";', self.shell)
        self.assertIn('input string InpT2LiveSymbols', self.shell)
        live = self.shell.split("input string InpT2LiveSymbols", 1)[1].split(";", 1)[0]
        self.assertNotIn("XAG", live)                  # the new assets are SHADOW until their own review

    def test_universe_appends_t2_only_symbols_while_t2_runs(self):
        body = section(self.shell, "int EEA_UniverseSymbols(string &out[])")
        self.assertIn("if(n<=0 || InpT2Mode==T2_OFF || InpT2OnlySymbols==\"\") return n;", body)
        self.assertIn("if(known || n>=EEA_RUNTIME_MAX_SYMBOLS) continue;", body)
        self.assertIn("int count = EEA_UniverseSymbols(canonical);", self.shell)      # OnInit
        self.assertIn("int count=EEA_UniverseSymbols(universe);", self.shell)          # panel choices
        self.assertIn("(int)InpT2Mode,InpT2OnlySymbols,(int)InpS07Mode", self.shell)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Runtime/StrategyCandidateRuntime.mqh").read_text(encoding="utf-8")

    def test_slot_for(self):
        body = section(self.src, "bool EEA_StrategyRuntimeSlotFor(")
        self.assertIn("if(!EEA_StrategyRuntimeSymbolListed(runtime.t2_only_symbols,canonical)) return true;", body)
        self.assertIn('return setup=="T2";', body)

    def test_init_and_sync_skip_the_other_slots(self):
        init = section(self.src, "bool EEA_StrategyCandidateRuntimeInitV1(")
        self.assertIn("runtime.t2_only_symbols=t2_only_symbols;", init)
        self.assertIn("if(!EEA_StrategyRuntimeSlotFor(runtime,p,canonical[i])) continue;", init)
        self.assertIn("runtime.symbol_count=engine_count;", init)
        sync = section(self.src, "bool EEA_StrategyRuntimeSyncSymbols(")
        self.assertEqual(sync.count("if(!EEA_StrategyRuntimeSlotFor(runtime,p,canonical[i])) continue;"), 2)
        self.assertIn("if(same && expected==runtime.symbol_count) return true;", sync)
        self.assertIn("next.symbol_count=e;", sync)

    def test_layout(self):
        full = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "USDJPY"]
        only = ("XAGUSD", "ETHUSD", "USOUSD")
        e = engines(full + list(only), only)
        self.assertEqual(len(e), 5 * 6 + 3)
        self.assertEqual([x for x in e if x[0] in only], [(s, "T2") for s in only])
        self.assertEqual(engines(full + list(only), only, t2=False), engines(full, only, t2=False))   # T2 OFF: nothing
        self.assertLessEqual(len(engines(full + list(only), only, s06=True)), 128)   # EEA_STRATEGY_RUNTIME_MAX_ENGINES

    def test_t2_live_still_by_list(self):
        mode = section(self.src, "int EEA_StrategyRuntimeEngineMode(")
        self.assertIn("!EEA_StrategyRuntimeSymbolListed(runtime.t2_live_symbols,runtime.engines[index].canonical_symbol))",
                      mode)


if __name__ == "__main__":
    unittest.main()
