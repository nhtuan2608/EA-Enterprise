"""Synthetic TC-046..051 checks; Python is a design oracle, not MQL5 proof."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import unittest

from pending_order_oracle import apply_broker_event, check_deadline, initialize, observe, observe_guard


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "Tests/Fixtures/pending-order-lifecycle-v0.1.0.json").read_text(encoding="utf-8"))


def bar(sequence, **changes):
    result = dict(DATA["observation_defaults"], closed_bar_sequence=sequence,
                  closed_at_utc=1000 + (sequence - 10) * 60,
                  bar_fingerprint=f"bar-{sequence}", setup_snapshot_id=f"setup-{sequence}")
    result.update(changes)
    return result


def event(kind, sequence, at_utc, **changes):
    result = dict(DATA["broker_event_defaults"], event_kind=kind,
                  event_id=f"event-{sequence}", event_sequence=sequence,
                  content_fingerprint=f"fingerprint-{sequence}", occurred_at_utc=at_utc,
                  correlation_id="", fill_volume=0, filled_initial_risk_money=0,
                  confirmed_remaining_volume=0)
    result.update(changes)
    return result


def guard(at_utc, **changes):
    result = dict(DATA["observation_defaults"], snapshot_id=f"guard-{at_utc}",
                  content_fingerprint=f"guard-fingerprint-{at_utc}",
                  observed_at_utc=at_utc)
    result.update(changes)
    return result


class PendingOrderOfflineTests(unittest.TestCase):
    def state(self, **changes):
        seed = deepcopy(DATA["seed"])
        seed.update(changes)
        return initialize(seed, 1001)

    def first_fill(self, state=None, at=1010):
        return apply_broker_event(state or self.state(),
                                  event("FILL", 1, at, fill_volume=0.1,
                                        filled_initial_risk_money=11.25))

    def test_initial_reservation_and_profile_validation(self):
        state = self.state()
        self.assertIsNotNone(state)
        self.assertEqual(state["effective_expires_at_utc"], 1300)
        self.assertEqual(state["remaining_risk_reservation_money"],
                         Decimal(str(DATA["expected_initial_risk_reservation_money"])))
        for change in ({"trade_style": "UNKNOWN"}, {"order_type": "BUY_STOP_LIMIT"},
                       {"broker_expiration_attested": False}, {"max_wait_closed_bars": 0},
                       {"requested_volume": 0.35}, {"max_committed_risk_money": 30},
                       {"order_ticket": ""}):
            with self.subTest(change=change):
                self.assertIsNone(self.state(**change))

    def test_all_four_pending_types_are_supported_by_contract(self):
        for kind in ("BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"):
            with self.subTest(kind=kind):
                self.assertEqual(self.state(order_type=kind)["order_type"], kind)

    def test_fill_in_acceptance_second_uses_sequence_not_second_precision(self):
        state, ok = apply_broker_event(self.state(), event("FILL", 1, 1000,
                                                           fill_volume=0.1,
                                                           filled_initial_risk_money=11.25))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "PARTIAL")

    def test_closed_bar_limit_requires_cancel_without_releasing_risk(self):
        state = self.state()
        for sequence in (11, 12, 13):
            state, ok = observe(state, bar(sequence))
            self.assertTrue(ok)
        self.assertEqual(state["bars_waited"], 3)
        self.assertEqual(state["status"], "CANCEL_REQUIRED")
        self.assertEqual(state["cancel_reason"], "MAX_WAIT_CLOSED_BARS_REACHED")
        self.assertEqual(state["remaining_risk_reservation_money"], Decimal("36.9"))
        self.assertTrue(state["new_entries_blocked"])
        again, ok = observe(state, bar(13))
        self.assertTrue(ok)
        self.assertEqual(again, state)

    def test_timer_reaches_utc_deadline_without_new_bar(self):
        state, ok = check_deadline(self.state(), 1299)
        self.assertTrue(ok)
        self.assertEqual(state["status"], "WORKING")
        state, ok = check_deadline(state, 1300)
        self.assertTrue(ok)
        self.assertEqual(state["status"], "CANCEL_REQUIRED")
        self.assertEqual(state["cancel_reason"], "UTC_DEADLINE_REACHED")
        self.assertEqual(state["bars_waited"], 0)

    def test_earliest_session_or_broker_expiration_wins(self):
        self.assertEqual(self.state(session_end_at_utc=1100)["effective_expires_at_utc"], 1100)
        self.assertEqual(self.state(broker_expiration_at_utc=1080)["effective_expires_at_utc"], 1080)
        self.assertIsNone(initialize(dict(DATA["seed"], setup_valid_until_utc=1001), 1001))

    def test_invalidation_requires_early_cancel(self):
        for key in ("setup_valid", "session_open", "risk_entry_allowed",
                    "news_entry_allowed", "quote_premise_valid", "config_spec_unchanged"):
            with self.subTest(key=key):
                state, ok = observe(self.state(), bar(11, **{key: False}))
                self.assertTrue(ok)
                self.assertEqual(state["status"], "CANCEL_REQUIRED")
                self.assertEqual(state["remaining_volume"], Decimal("0.3"))

    def test_guard_update_between_bars_cancels_and_duplicate_is_idempotent(self):
        first = guard(1030, quote_premise_valid=False)
        state, ok = observe_guard(self.state(), first)
        self.assertTrue(ok)
        self.assertEqual(state["status"], "CANCEL_REQUIRED")
        self.assertEqual(state["bars_waited"], 0)
        again, ok = observe_guard(state, first)
        self.assertTrue(ok)
        self.assertEqual(again, state)
        conflict, ok = observe_guard(state, dict(first, content_fingerprint="revised"))
        self.assertFalse(ok)
        self.assertEqual(conflict["status"], "PENDING_RACE_UNKNOWN")
        unknown, ok = observe_guard(self.state(), guard(1000))
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")

    def test_partial_fill_keeps_original_deadline_and_risk(self):
        state, ok = self.first_fill()
        self.assertTrue(ok)
        self.assertEqual(state["status"], "PARTIAL")
        for key, value in DATA["expected_partial"].items():
            self.assertEqual(state[key], Decimal(str(value)), key)
        state, _ = check_deadline(state, 1300)
        self.assertEqual(state["status"], "CANCEL_REQUIRED")
        self.assertEqual(state["remaining_risk_reservation_money"], Decimal("24.6"))
        state, ok = apply_broker_event(state, event("CANCEL_REQUESTED", 2, 1301,
                                                   correlation_id="cancel-1"))
        self.assertTrue(ok)
        self.assertEqual(state["remaining_risk_reservation_money"], Decimal("24.6"))
        state, ok = apply_broker_event(state, event("CANCEL_CONFIRMED", 3, 1302,
                                                   correlation_id="cancel-1",
                                                   confirmed_remaining_volume=0.2))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "CANCELLED")
        self.assertEqual(state["filled_volume"], Decimal("0.1"))
        self.assertEqual(state["cancelled_volume"], Decimal("0.2"))
        self.assertEqual(state["remaining_risk_reservation_money"], 0)
        self.assertEqual(state["total_committed_risk_money"], Decimal("11.25"))

    def test_cancel_request_without_confirmation_does_not_release_risk(self):
        state, _ = check_deadline(self.state(), 1300)
        state, _ = apply_broker_event(state, event("CANCEL_REQUESTED", 1, 1301,
                                                  correlation_id="cancel-1"))
        self.assertEqual(state["status"], "CANCEL_REQUESTED")
        self.assertEqual(state["remaining_volume"], Decimal("0.3"))
        self.assertEqual(state["remaining_risk_reservation_money"], Decimal("36.9"))
        bad, ok = apply_broker_event(state, event("CANCEL_CONFIRMED", 2, 1302,
                                                 correlation_id="cancel-1",
                                                 confirmed_remaining_volume=0.2))
        self.assertFalse(ok)
        self.assertEqual(bad["status"], "PENDING_RACE_UNKNOWN")
        self.assertEqual(bad["remaining_risk_reservation_money"], Decimal("36.9"))

    def test_expiration_confirmation_releases_only_attested_remainder(self):
        state, _ = check_deadline(self.state(), 1300)
        state, ok = apply_broker_event(state, event("EXPIRE_CONFIRMED", 1, 1301,
                                                   confirmed_remaining_volume=0.3))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "EXPIRED")
        self.assertEqual(state["cancelled_volume"], Decimal("0.3"))
        self.assertEqual(state["total_committed_risk_money"], 0)
        late, ok = apply_broker_event(state, event("FILL", 2, 1302,
                                                  fill_volume=0.1,
                                                  filled_initial_risk_money=11.25))
        self.assertFalse(ok)
        self.assertEqual(late["status"], "PENDING_RACE_UNKNOWN")

    def test_broker_expiration_can_be_reconciled_after_local_timer_was_missed(self):
        state, ok = apply_broker_event(self.state(), event("EXPIRE_CONFIRMED", 1, 1500,
                                                           confirmed_remaining_volume=0.3))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "EXPIRED")
        self.assertEqual(state["broker_confirmed_at_utc"], 1500)
        self.assertTrue(state["new_entries_blocked"])

    def test_fill_during_cancel_is_recorded_and_needs_review(self):
        state, _ = check_deadline(self.state(), 1300)
        state, _ = apply_broker_event(state, event("CANCEL_REQUESTED", 1, 1301,
                                                  correlation_id="cancel-1"))
        state, ok = apply_broker_event(state, event("FILL", 2, 1302,
                                                   fill_volume=0.1,
                                                   filled_initial_risk_money=11.25))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "BREACH_REVIEW")
        self.assertEqual(state["filled_volume"], Decimal("0.1"))
        self.assertEqual(state["remaining_risk_reservation_money"], Decimal("24.6"))
        state, ok = apply_broker_event(state, event("CANCEL_CONFIRMED", 3, 1303,
                                                   correlation_id="cancel-1",
                                                   confirmed_remaining_volume=0.2))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "BREACH_REVIEW")
        self.assertTrue(state["new_entries_blocked"])

    def test_duplicate_conflict_gap_and_unclosed_bar_fail_closed(self):
        state, _ = self.first_fill()
        original = event("FILL", 1, 1010, fill_volume=0.1,
                         filled_initial_risk_money=11.25)
        duplicate, ok = apply_broker_event(state, original)
        self.assertTrue(ok)
        self.assertEqual(duplicate, state)
        changed = dict(original, content_fingerprint="different")
        unknown, ok = apply_broker_event(state, changed)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
        foreign = dict(event("FILL", 2, 1020, fill_volume=0.1,
                             filled_initial_risk_money=11.25), order_ticket="another-ticket")
        unknown, ok = apply_broker_event(state, foreign)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
        for bad_bar in (bar(12), bar(11, bar_closed_confirmed=False)):
            unknown, ok = observe(self.state(), bad_bar)
            self.assertFalse(ok)
            self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")

    def test_full_fill_and_risk_breach(self):
        state, _ = self.first_fill()
        state, ok = apply_broker_event(state, event("FILL", 2, 1020,
                                                   fill_volume=0.2,
                                                   filled_initial_risk_money=23.5))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "FILLED")
        self.assertEqual(state["total_committed_risk_money"], Decimal("34.75"))
        state, _ = self.first_fill()
        state, ok = apply_broker_event(state, event("FILL", 2, 1020,
                                                   fill_volume=0.1,
                                                   filled_initial_risk_money=45))
        self.assertTrue(ok)
        self.assertEqual(state["status"], "BREACH_REVIEW")
        self.assertGreater(state["total_committed_risk_money"], Decimal("50"))

    def test_source_is_isolated_from_live_order_apis(self):
        source = (ROOT / "TradeManager/PendingOrderLifecycle.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        for forbidden in ("OrderSend(", "CTrade ", "WebRequest(", "FileOpen("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("PendingOrderLifecycle.mqh", shell)


if __name__ == "__main__":
    unittest.main()
