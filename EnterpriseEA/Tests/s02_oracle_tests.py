"""Fixed-fixture oracle for S02; passing this suite is not MQL5 runtime proof."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from s02_oracle import checkpoint, new_engine, process

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/s02-observer-v0.1.0.json").read_text(encoding="utf-8"))


def run_case(case: dict) -> tuple[list[dict], dict]:
    engine = new_engine(FIXTURE["identity"], FIXTURE["config"])
    events = []
    for source in case["bars"]:
        bar = dict(source, atr=FIXTURE["atr"])
        events.append(process(engine, bar, FIXTURE["key_level"], FIXTURE["config"]))
    return events, engine


class S02ObserverOracle(unittest.TestCase):
    def assert_case_matches_fixture(self, name: str):
        case = FIXTURE["cases"][name]
        actual, engine = run_case(case)
        expected = case["expected"]
        self.assertEqual(len(actual), len(expected))
        for index, (observed, wanted) in enumerate(zip(actual, expected)):
            with self.subTest(case=name, bar=index):
                self.assertEqual(observed["event"], wanted["event"])
                self.assertEqual(observed["state"], wanted["state"])
                self.assertEqual(observed["reason"], wanted["reason"])
        return actual, engine

    def test_valid_closed_bar_sequence_and_candidate_scope(self):
        events, engine = self.assert_case_matches_fixture("valid_sequence_and_candidate_ttl")
        candidate = engine["candidate"]
        expected = FIXTURE["cases"]["valid_sequence_and_candidate_ttl"]["candidate_at_trigger"]
        triggered = events[3]["candidate_id"]
        self.assertIn("-FIXTURE_XYZ-FIXTURE-", triggered)
        self.assertEqual(candidate["direction"], expected["direction"])
        self.assertEqual(candidate["key_level"], expected["key_level"])
        self.assertEqual(candidate["invalidation_price"], expected["invalidation_price"])
        self.assertEqual(events[3]["state"], "TRIGGERED")
        self.assertFalse(expected["eligible"])
        self.assertNotIn("target", candidate)

    def test_missing_retest_expires_with_reason(self):
        _, engine = self.assert_case_matches_fixture("missing_retest_expires")
        self.assertEqual(engine["state"], "EXPIRED")
        self.assertEqual(engine["candidate"]["reason_code"], "NO_RETEST_WITHIN_WINDOW")

    def test_short_sequence_triggers_with_above_level_invalidation(self):
        _, engine = self.assert_case_matches_fixture("short_sequence_triggers")
        self.assertEqual(engine["candidate"]["direction"], "SHORT")
        self.assertEqual(engine["candidate"]["invalidation_price"], 101.0)
        self.assertEqual(engine["candidate"]["state"], "TRIGGERED")

    def test_acceptance_timeout_expires_without_trigger(self):
        _, engine = self.assert_case_matches_fixture("acceptance_not_confirmed")
        self.assertEqual(engine["state"], "EXPIRED")
        self.assertEqual(engine["candidate"]["triggered_at"], None)

    def test_failed_hold_invalidates(self):
        _, engine = self.assert_case_matches_fixture("failed_hold_invalidates")
        self.assertEqual(engine["state"], "INVALIDATED")
        self.assertEqual(engine["candidate"]["reason_code"], "RETEST_CLOSED_THROUGH_INVALIDATION")

    def test_duplicate_bar_is_ignored_without_mutating_engine(self):
        case = FIXTURE["cases"]["duplicate_closed_bar_is_ignored"]
        engine = new_engine(FIXTURE["identity"], FIXTURE["config"])
        first = dict(case["bars"][0], atr=FIXTURE["atr"])
        event = process(engine, first, FIXTURE["key_level"], FIXTURE["config"])
        self.assertEqual(event["event"], case["expected"][0]["event"])
        before = checkpoint(engine)
        duplicate = process(engine, dict(case["bars"][1], atr=FIXTURE["atr"]), FIXTURE["key_level"], FIXTURE["config"])
        self.assertEqual(duplicate["reason"], "DUPLICATE_CLOSED_BAR")
        self.assertEqual(engine, before)

    def test_restart_parity_from_retest_state(self):
        case = FIXTURE["cases"]["valid_sequence_and_candidate_ttl"]
        engine = new_engine(FIXTURE["identity"], FIXTURE["config"])
        for source in case["bars"][:3]:
            process(engine, dict(source, atr=FIXTURE["atr"]), FIXTURE["key_level"], FIXTURE["config"])
        restored = checkpoint(engine)
        next_bar = dict(case["bars"][3], atr=FIXTURE["atr"])
        uninterrupted_event = process(engine, next_bar, FIXTURE["key_level"], FIXTURE["config"])
        restarted_event = process(restored, next_bar, FIXTURE["key_level"], FIXTURE["config"])
        self.assertEqual(restarted_event, uninterrupted_event)
        self.assertEqual(restored, engine)

    def test_mql_module_is_isolated_and_observer_only(self):
        source = (ROOT / "Setups/BreakRetest.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_S02ProcessClosedBar", source)
        self.assertIn("DUPLICATE_CLOSED_BAR", source)
        self.assertIn("RETEST_CLOSED_THROUGH_INVALIDATION", source)
        self.assertNotIn("BreakRetest.mqh", shell)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
