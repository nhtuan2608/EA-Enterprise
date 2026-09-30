"""Synthetic append-only audit contract for pending-order transitions."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import unittest

from pending_audit_oracle import accept, cursor_defaults, fingerprint, make_record
from pending_checkpoint_oracle import make_checkpoint, restore
from pending_order_oracle import apply_broker_event, check_deadline, initialize, observe


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "Tests/Fixtures/pending-order-lifecycle-v0.1.0.json").read_text(encoding="utf-8"))
AUDIT = json.loads((ROOT / "Tests/Fixtures/pending-order-audit-v1.0.0.json").read_text(encoding="utf-8"))
IDENTITY = {k: DATA["seed"][k] for k in
            ("intent_id", "config_version", "broker_server", "account_fingerprint", "order_ticket")}


def initial():
    return initialize(DATA["seed"], 1001)


def bar(sequence):
    return dict(DATA["observation_defaults"], closed_bar_sequence=sequence,
                closed_at_utc=1000 + (sequence - 10) * 60,
                bar_fingerprint=f"audit-bar-{sequence}",
                setup_snapshot_id=f"audit-setup-{sequence}")


def broker_event(kind, sequence, at_utc, **changes):
    result = dict(DATA["broker_event_defaults"], event_kind=kind,
                  event_id=f"audit-broker-{sequence}", event_sequence=sequence,
                  content_fingerprint=f"audit-broker-fingerprint-{sequence}",
                  occurred_at_utc=at_utc, data_quality="OK", correlation_id="",
                  fill_volume=0, filled_initial_risk_money=0, confirmed_remaining_volume=0)
    result.update(changes)
    return result


def record(before, after, cause, sequence=1, previous="", occurred=1060, observed=1061, **changes):
    return make_record(before, after, cause, sequence, previous,
                       event_id=f"audit-{sequence}", occurred_at_utc=occurred,
                       observed_at_utc=observed,
                       source_fingerprint=AUDIT["source_fingerprint"], **changes)


def start_chain():
    after = initial()
    before = deepcopy(after)
    before.update(initialized=False, status="UNKNOWN", reason_code="ATTESTED_PENDING_SEED_REQUIRED",
                  requested_volume=Decimal(0), filled_volume=Decimal(0),
                  cancelled_volume=Decimal(0), remaining_volume=Decimal(0),
                  filled_initial_risk_money=Decimal(0),
                  remaining_risk_reservation_money=Decimal(0),
                  total_committed_risk_money=Decimal(0), effective_expires_at_utc=0)
    row = record(before, after, "SEED_ACCEPTED", occurred=1000, observed=1001)
    accepted, cursor, ok = accept(before, after, row, cursor_defaults())
    assert ok
    return accepted, cursor


class PendingAuditTests(unittest.TestCase):
    def test_initial_acceptance_starts_the_audit_chain(self):
        accepted, cursor = start_chain()
        self.assertEqual(accepted["status"], "WORKING")
        self.assertEqual(cursor["last_sequence"], 1)

    def test_missing_initial_acceptance_is_a_gap(self):
        before = initial()
        after, _ = observe(before, bar(11))
        row = record(before, after, "BAR")
        unknown, cursor, ok = accept(before, after, row, cursor_defaults())
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(cursor["blocked"])

    def test_bar_fill_cancel_chain_keeps_volume_and_risk_lineage(self):
        before, cursor = start_chain()
        after, ok = observe(before, bar(11))
        self.assertTrue(ok)
        row = record(before, after, "BAR", 2, cursor["last_fingerprint"])
        after, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(cursor["last_sequence"], 2)
        self.assertEqual(after["bars_waited"], 1)

        before = after
        after, ok = apply_broker_event(before, broker_event("FILL", 1, 1070,
                                                             fill_volume=0.1,
                                                             filled_initial_risk_money=11.25))
        self.assertTrue(ok)
        row = record(before, after, "BROKER_FILL", 3, cursor["last_fingerprint"], 1070, 1071)
        after, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(after["remaining_risk_reservation_money"], Decimal("24.6"))

        before = after
        after, _ = check_deadline(before, 1300)
        row = record(before, after, "TIMER", 4, cursor["last_fingerprint"], 1300, 1301)
        after, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(after["status"], "CANCEL_REQUIRED")

        before = after
        after, _ = apply_broker_event(before, broker_event("CANCEL_REQUESTED", 2, 1302,
                                                            correlation_id="cancel-audit"))
        row = record(before, after, "CANCEL_REQUEST", 5, cursor["last_fingerprint"], 1302, 1303)
        after, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(after["remaining_risk_reservation_money"], Decimal("24.6"))

        before = after
        after, _ = apply_broker_event(before, broker_event("CANCEL_CONFIRMED", 3, 1304,
                                                            correlation_id="cancel-audit",
                                                            confirmed_remaining_volume=0.2))
        row = record(before, after, "BROKER_TERMINAL", 6, cursor["last_fingerprint"], 1304, 1305)
        after, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(after["status"], "CANCELLED")
        self.assertEqual(after["filled_volume"], Decimal("0.1"))
        self.assertEqual(after["cancelled_volume"], Decimal("0.2"))
        self.assertEqual(cursor["last_sequence"], 6)

    def test_duplicate_exact_record_is_idempotent(self):
        before, cursor = start_chain()
        after, _ = observe(before, bar(11))
        row = record(before, after, "BAR", 2, cursor["last_fingerprint"])
        accepted, cursor, ok = accept(before, after, row, cursor)
        self.assertTrue(ok)
        again, same_cursor, ok = accept(before, accepted, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(again, accepted)
        self.assertEqual(same_cursor, cursor)

    def test_tamper_gap_or_same_sequence_conflict_blocks_entry(self):
        before, seed_cursor = start_chain()
        after, _ = observe(before, bar(11))
        first = record(before, after, "BAR", 2, seed_cursor["last_fingerprint"])
        _, cursor, ok = accept(before, after, first, seed_cursor)
        self.assertTrue(ok)
        for label, mutate, resign in (
                ("raw tamper", lambda r: r.__setitem__("remaining_volume_after", 0.1), False),
                ("signed volume lie", lambda r: r.__setitem__("remaining_volume_after", 0.1), True),
                ("sequence gap", lambda r: r.__setitem__("audit_sequence", 3), True),
                ("chain mismatch", lambda r: r.__setitem__("previous_fingerprint", "wrong"), True),
                ("same sequence conflict", lambda r: r.__setitem__("event_id", "different"), True),
                ("untrusted successful transition", lambda r: r.__setitem__("data_quality", "UNTRUSTED"), True)):
            with self.subTest(label=label):
                bad = deepcopy(first)
                mutate(bad)
                if resign:
                    bad["fingerprint"] = fingerprint(bad)
                unknown, blocked_cursor, ok = accept(before, after, bad, cursor)
                self.assertFalse(ok)
                self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
                self.assertTrue(unknown["new_entries_blocked"])
                self.assertTrue(blocked_cursor["blocked"])

    def test_timer_cannot_forge_released_reservation(self):
        before, cursor = start_chain()
        after, _ = check_deadline(before, 1300)
        after["remaining_risk_reservation_money"] = 0
        row = record(before, after, "TIMER", 2, cursor["last_fingerprint"], 1300, 1301)
        unknown, cursor, ok = accept(before, after, row, cursor)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(cursor["blocked"])

    def test_fill_cannot_reduce_recorded_initial_risk(self):
        before, cursor = start_chain()
        after, ok = apply_broker_event(before, broker_event("FILL", 1, 1010,
                                                             fill_volume=0.1,
                                                             filled_initial_risk_money=11.25))
        self.assertTrue(ok)
        after["filled_initial_risk_money"] = Decimal(0)
        row = record(before, after, "BROKER_FILL", 2, cursor["last_fingerprint"], 1010, 1011)
        unknown, blocked_cursor, ok = accept(before, after, row, cursor)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(blocked_cursor["blocked"])

    def test_wrong_ticket_rejected_even_with_matching_hash(self):
        before, cursor = start_chain()
        after, _ = observe(before, bar(11))
        row = record(before, after, "BAR", 2, cursor["last_fingerprint"])
        row["order_ticket"] = "foreign-ticket"
        row["fingerprint"] = fingerprint(row)
        unknown, _, ok = accept(before, after, row, cursor)
        self.assertFalse(ok)
        self.assertEqual(unknown["status"], "PENDING_RACE_UNKNOWN")

    def test_reconciliation_evidence_is_audited_without_unlocking_entries(self):
        base, cursor = start_chain()
        anchor = dict(audit_sequence=cursor["last_sequence"],
                      audit_fingerprint=cursor["last_fingerprint"],
                      audit_event_id=cursor["last_event_id"],
                      audit_observed_at_utc=cursor["last_observed_at_utc"])
        checkpoint = make_checkpoint(base, 7, 1050, 300, anchor)
        restored, _, ok, _ = restore(None, checkpoint, IDENTITY, 1060)
        self.assertTrue(ok)
        restore_row = record(base, restored, "RESTORE", 2, cursor["last_fingerprint"], 1060, 1061)
        restored, cursor, ok = accept(base, restored, restore_row, cursor)
        self.assertTrue(ok)
        row = record(restored, restored, "RECONCILE_EVIDENCE", 3, cursor["last_fingerprint"],
                     1062, 1063,
                     broker_snapshot_id="broker-snapshot-1",
                     order_history_fingerprint="order-history-1",
                     deal_set_fingerprint="deal-set-1")
        still_unknown, _, ok = accept(restored, restored, row, cursor)
        self.assertTrue(ok)
        self.assertEqual(still_unknown["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(still_unknown["new_entries_blocked"])
        missing = dict(row, deal_set_fingerprint="")
        missing["fingerprint"] = fingerprint(missing)
        unknown, _, ok = accept(restored, restored, missing, cursor)
        self.assertFalse(ok)
        self.assertTrue(unknown["new_entries_blocked"])

    def test_audit_source_is_isolated_from_ea_shell(self):
        source = (ROOT / "Storage/PendingOrderAudit.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_PendingAuditAccept", source)
        for forbidden in ("OrderSend(", "FileOpen(", "HistorySelect(", "WebRequest("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("PendingOrderAudit.mqh", shell)


if __name__ == "__main__":
    unittest.main()
