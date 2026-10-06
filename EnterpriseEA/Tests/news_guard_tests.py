"""News Guard: state machine (TC-NG-01..11) and its integration."""
import unittest
from pathlib import Path

from news_guard_oracle import config, symbol_currencies, evaluate, entry_block, break_even_due, indirect_window


ROOT = Path(__file__).resolve().parents[1]
T = 1791460800  # an event time (UTC)
MIN = 60


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


class NewsStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.c = config()
        self.usd = [(T, "USD")]

    def state_at(self, offset_min, normalized=0):
        return evaluate(self.usd, ["USD"], T + offset_min * MIN, self.c, normalized)[0]

    def test_countdown_follows_d1_windows(self):  # TC-NG-01 / TC-018
        expected = [(-181, "NORMAL"), (-180, "PRE_NEWS"), (-61, "PRE_NEWS"), (-60, "PRE_NEWS_BLOCK"),
                    (-1, "PRE_NEWS_BLOCK"), (0, "ACTIVE"), (4, "ACTIVE"), (5, "POST_NEWS"),
                    (14, "POST_NEWS"), (15, "NORMALIZING"), (59, "NORMALIZING"), (60, "NORMAL")]
        for offset, state in expected:
            with self.subTest(offset=offset):
                self.assertEqual(self.state_at(offset), state)

    def test_normalization_ends_early_once_stable(self):  # TC-NG-09
        self.assertEqual(self.state_at(20, normalized=T), "NORMAL")
        self.assertEqual(self.state_at(20, normalized=T - 1), "NORMALIZING")

    def test_profile_windows(self):  # TC-NG-08
        self.assertEqual(entry_block("PRE_NEWS", "SWING", self.c), "NEWS_PRE_BLOCK_SWING")
        self.assertEqual(entry_block("PRE_NEWS", "SCALP", self.c), "")
        self.assertEqual(entry_block("PRE_NEWS_BLOCK", "SCALP", self.c), "NEWS_PRE_BLOCK_SCALP")
        for state, reason in (("ACTIVE", "NEWS_ACTIVE"), ("POST_NEWS", "NEWS_POST"),
                              ("NORMALIZING", "NEWS_NORMALIZING")):
            for profile in ("SCALP", "SWING"):
                self.assertEqual(entry_block(state, profile, self.c), reason)
        self.assertEqual(entry_block("NORMAL", "SWING", self.c), "")

    def test_unknown_blocks_unless_operator_allows(self):  # TC-NG-02 / D3
        self.assertEqual(entry_block("UNKNOWN", "SCALP", self.c), "NEWS_UNKNOWN")
        self.assertEqual(entry_block("UNKNOWN", "SCALP", config(allow_when_unknown=True)), "")

    def test_disabled_guard_never_blocks(self):  # TC-NG-12
        self.assertEqual(entry_block("ACTIVE", "SCALP", config(enabled=False)), "")

    def test_currency_mapping(self):  # TC-NG-03
        self.assertEqual(symbol_currencies("EUR", "USD"), ["EUR", "USD"])
        self.assertEqual(symbol_currencies("XAU", "USD"), ["USD"])
        self.assertEqual(symbol_currencies("BTC", "USD"), ["USD"])
        self.assertEqual(symbol_currencies("USD", "JPY"), ["USD", "JPY"])
        state, _ = evaluate([(T, "EUR")], symbol_currencies("XAU", "USD"), T, self.c)
        self.assertEqual(state, "NORMAL")

    def test_close_events_merge_into_one_window(self):  # TC-NG-04
        events = [(T, "USD"), (T + 20 * MIN, "USD")]
        for offset in range(-60, 35):
            state, _ = evaluate(events, ["USD"], T + offset * MIN, self.c)
            self.assertNotEqual(state, "NORMAL", offset)
        # The strictest state wins: 15 minutes after the first event the second is close.
        self.assertEqual(evaluate(events, ["USD"], T + 16 * MIN, self.c)[0], "PRE_NEWS_BLOCK")

    def test_break_even_window(self):  # TC-NG-07 timing (D2)
        self.assertFalse(break_even_due(self.usd, ["USD"], T - 16 * MIN, self.c))
        self.assertTrue(break_even_due(self.usd, ["USD"], T - 15 * MIN, self.c))
        self.assertTrue(break_even_due(self.usd, ["USD"], T + 14 * MIN, self.c))
        self.assertFalse(break_even_due(self.usd, ["USD"], T + 15 * MIN, self.c))


class IndirectYellowTests(unittest.TestCase):
    def test_yellow_windows(self):
        c = config()
        ecb = [(T, "EUR", True)]
        xau = ["USD"]
        self.assertEqual(indirect_window(ecb, xau, T - 181 * MIN, c), (False, False))
        self.assertEqual(indirect_window(ecb, xau, T - 180 * MIN, c), (True, False))
        self.assertEqual(indirect_window(ecb, xau, T - 60 * MIN, c), (True, True))
        self.assertEqual(indirect_window(ecb, xau, T + 14 * MIN, c), (True, True))
        self.assertEqual(indirect_window(ecb, xau, T + 15 * MIN, c), (False, False))
        # Own currency is red, not yellow; non-strength sectors are ignored.
        self.assertEqual(indirect_window([(T, "USD", True)], xau, T, c), (False, False))
        self.assertEqual(indirect_window([(T, "EUR", False)], xau, T, c), (False, False))

    def test_yellow_policy_in_source(self):
        cal = read("News/NewsCalendar.mqh")
        block = section(cal, "string EEA_NewsEntryBlockFor")
        self.assertIn('if(profile=="SWING" && rt.symbols[i].indirect_swing_blocked) return "NEWS_INDIRECT_SWING";', block)
        factor = section(cal, "double EEA_NewsRiskFactorFor")
        self.assertIn('profile=="SWING"', factor)
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn("EEA_ControlledLiveApplyNewsRisk(news,", live)
        pending = section(live, "void EEA_PendingApplyNews")
        self.assertIn("EEA_NewsDirectBlockFor(", pending)           # yellow never cancels pending orders
        self.assertNotIn("EEA_NewsEntryBlockFor(", pending)
        state = read("News/NewsState.mqh")
        self.assertIn("c.indirect_scalp_factor=0.5;", state)


class NewsStateParityTests(unittest.TestCase):
    def setUp(self):
        self.mql = read("News/NewsState.mqh")

    def test_defaults_match_confirmed_decisions(self):
        defaults = section(self.mql, "void EEA_NewsConfigDefaults")
        for token in ("c.scalp_block_before_min=60", "c.swing_block_before_min=180", "c.active_min=5",
                      "c.post_min=15", "c.max_normalize_min=60", "c.be_before_min=15", "c.be_min_r=0.3",
                      "c.allow_when_unknown=false"):
            self.assertIn(token, defaults)

    def test_mql_state_machine_matches_oracle_order(self):
        body = section(self.mql, "string EEA_NewsEventState")
        order = [body.index('"' + s + '"') for s in
                 ("ACTIVE", "POST_NEWS", "PRE_NEWS_BLOCK", "NORMALIZING", "PRE_NEWS")]
        self.assertEqual(order, sorted(order))
        block = section(self.mql, "string EEA_NewsEntryBlock")
        self.assertIn('if(state=="UNKNOWN") return c.allow_when_unknown ? "" : "NEWS_UNKNOWN";', block)


class NewsIntegrationTests(unittest.TestCase):
    def test_calendar_unknown_is_never_normal(self):
        cal = read("News/NewsCalendar.mqh")
        update = section(cal, "void EEA_NewsUpdate")
        self.assertIn('"UNKNOWN"', update)
        self.assertIn("EEA_NEWS_STALE_SECONDS", update)
        refresh = section(cal, "bool EEA_NewsRefreshCalendar")
        self.assertIn("CalendarValueHistory(", refresh)
        self.assertIn("CALENDAR_IMPORTANCE_HIGH", refresh)
        self.assertIn('"NEWS_CALENDAR_EMPTY"', refresh)

    def test_live_loop_blocks_and_caps_pending_expiry(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        on_timer = live.split("bool EEA_ControlledLiveOnTimer", 1)[1]
        self.assertIn("EEA_NewsEntryBlockFor(news,", on_timer)
        self.assertIn("EEA_ControlledLiveApplyNewsExpiry(news,", on_timer)
        cap = section(live, "bool EEA_ControlledLiveApplyNewsExpiry")
        self.assertIn('"NEWS_WINDOW_TOO_CLOSE"', cap)

    def test_pending_cancel_and_break_even_use_the_guard(self):
        live = read("Integration/ControlledLiveRuntime.mqh")
        apply = section(live, "void EEA_PendingApplyNews")
        self.assertIn("g.news_entry_allowed=false", apply)
        self.assertIn("EEA_PendingObserveGuard(", apply)
        tm = read("Runtime/TradeManagerRuntime.mqh")
        self.assertIn('"NEWS_BREAK_EVEN"', tm)
        self.assertIn("EEA_NewsBreakEvenDueFor(news,", tm)
        self.assertNotIn("NEWS_CLOSE", tm)  # D5: never close because of news


class AuditFieldOrderTests(unittest.TestCase):
    """EEAEvent_Init(e,type,now,symbol,entity,before,after,quality): symbols go in the symbol field."""

    def test_new_audit_events_put_the_symbol_in_the_symbol_field(self):
        cases = {
            "News/NewsCalendar.mqh": "EEAEvent_Init(event,event_type,TimeGMT(),symbol,\"\",before,after,\"OK\");",
            "Runtime/TradeManagerRuntime.mqh": "EEAEvent_Init(event,event_type,TimeGMT(),t.intent.canonical_symbol,",
            "Integration/ControlledLiveRuntime.mqh": 'EEAEvent_Init(event,"NEWS_ENTRY_BLOCKED",TimeGMT(),strategy.engines[i].canonical_symbol,',
        }
        for path, call in cases.items():
            self.assertIn(call, read(path), path)
        live = read("Integration/ControlledLiveRuntime.mqh")
        self.assertIn('EEAEvent_Init(event,"LIVE_AUTHORIZATION_BOUND",TimeGMT(),decision.symbol,', live)
        self.assertIn('EEAEvent_Init(event,"NEWS_PENDING_CANCEL",TimeGMT(),t.state.canonical_symbol,', live)


class NewsIgnoreListTests(unittest.TestCase):
    def test_ignore_list_is_empty_by_default_and_case_insensitive(self):
        state = read("News/NewsState.mqh")
        self.assertIn('c.ignore_keywords="";', state)
        ignored = section(state, "bool EEA_NewsEventIgnored")
        self.assertIn('if(keywords=="") return false;', ignored)
        self.assertIn("StringToLower(lowered);", ignored)
        shell = read("EnterpriseEA.mq5")
        self.assertIn('input string InpNewsIgnoreKeywords      = "Initial Jobless Claims,EIA Crude Oil,', shell)
        cal = read("News/NewsCalendar.mqh")
        self.assertIn("EEA_NewsEventIgnored(ev.name,rt.cfg.ignore_keywords)", cal)

    def test_state_changes_fill_before_after_and_config(self):
        cal = read("News/NewsCalendar.mqh")
        self.assertIn('"NEWS_STATE_CHANGED",s.canonical,before,s.state,', cal)
        self.assertIn("event.config_version=config_version;", cal)


if __name__ == "__main__":
    unittest.main()
