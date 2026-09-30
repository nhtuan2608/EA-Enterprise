"""Synthetic restart contract for pending orders; no terminal or broker I/O."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import unittest

from pending_checkpoint_oracle import fingerprint, make_checkpoint, restore, verify_audit_tail
from pending_audit_oracle import accept, cursor_defaults, make_record, fingerprint as audit_fingerprint
from pending_order_oracle import apply_broker_event, check_deadline, initialize, observe


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "Tests/Fixtures/pending-order-lifecycle-v0.1.0.json").read_text(encoding="utf-8"))
DATA = json.loads((ROOT / "Tests/Fixtures/pending-order-checkpoint-v1.1.0.json").read_text(encoding="utf-8"))


def checkpoint(state=None):
    s = state if state is not None else initialize(SEED["seed"], 1001)
    return make_checkpoint(s, DATA["checkpoint_sequence"], DATA["captured_at_utc"],
                           DATA["max_age_seconds"], DATA["audit_anchor"])


def event(kind, seq, at_utc, **changes):
    result = dict(SEED["broker_event_defaults"], event_kind=kind,
                  event_id=f"checkpoint-event-{seq}", event_sequence=seq,
                  content_fingerprint=f"checkpoint-fingerprint-{seq}",
                  occurred_at_utc=at_utc, correlation_id="", fill_volume=0,
                  filled_initial_risk_money=0, confirmed_remaining_volume=0)
    result.update(changes)
    return result


class PendingCheckpointTests(unittest.TestCase):
    def test_partial_restore_preserves_deadline_volume_risk_and_event_cursor(self):
        partial, ok = apply_broker_event(initialize(SEED["seed"], 1001),
                                         event("FILL", 1, 1010, fill_volume=0.1,
                                               filled_initial_risk_money=11.25))
        self.assertTrue(ok)
        restored, guard, ok, reason = restore(None, checkpoint(partial),
                                               DATA["expected_identity"], DATA["restore_at_utc"])
        self.assertTrue(ok)
        self.assertEqual(reason, "PENDING_CHECKPOINT_RESTORED_RECONCILIATION_REQUIRED")
        self.assertEqual(restored["status"], "PENDING_RACE_UNKNOWN")
        self.assertEqual(restored["effective_expires_at_utc"], 1300)
        self.assertEqual(restored["filled_volume"], Decimal("0.1"))
        self.assertEqual(restored["remaining_volume"], Decimal("0.2"))
        self.assertEqual(restored["remaining_risk_reservation_money"], Decimal("24.6"))
        self.assertEqual(restored["last_event_sequence"], 1)
        self.assertTrue(restored["new_entries_blocked"])
        self.assertTrue(guard["initialized"])
        later, ok = check_deadline(restored, 1300)
        self.assertTrue(ok)
        self.assertEqual(later["status"], "PENDING_RACE_UNKNOWN")

    def test_cancel_request_restore_keeps_remainder_reserved(self):
        state, _ = check_deadline(initialize(SEED["seed"], 1001), 1300)
        state, ok = apply_broker_event(state, event("CANCEL_REQUESTED", 1, 1301,
                                                   correlation_id="cancel-1"))
        self.assertTrue(ok)
        c = make_checkpoint(state, 7, 1302, 300, DATA["audit_anchor"])
        restored, _, ok, _ = restore(None, c, DATA["expected_identity"], 1303)
        self.assertTrue(ok)
        self.assertEqual(restored["cancel_correlation_id"], "cancel-1")
        self.assertEqual(restored["cancel_requested_at_utc"], 1301)
        self.assertEqual(restored["remaining_risk_reservation_money"], Decimal("36.9"))
        self.assertTrue(restored["new_entries_blocked"])

    def test_restart_does_not_reset_closed_bar_wait_count(self):
        state = initialize(SEED["seed"], 1001)
        for sequence in (11, 12):
            bar = dict(SEED["observation_defaults"], closed_bar_sequence=sequence,
                       closed_at_utc=1000 + (sequence - 10) * 60,
                       bar_fingerprint=f"checkpoint-bar-{sequence}",
                       setup_snapshot_id=f"checkpoint-setup-{sequence}")
            state, ok = observe(state, bar)
            self.assertTrue(ok)
        c = make_checkpoint(state, 7, 1121, 300, DATA["audit_anchor"])
        restored, _, ok, _ = restore(None, c, DATA["expected_identity"], 1122)
        self.assertTrue(ok)
        self.assertEqual(restored["bars_waited"], 2)
        self.assertEqual(restored["last_closed_bar_sequence"], 12)
        self.assertEqual(restored["effective_expires_at_utc"], 1300)
        self.assertEqual(restored["status"], "PENDING_RACE_UNKNOWN")

    def test_torn_tampered_or_missing_checkpoint_blocks_entries(self):
        base = checkpoint()
        for label, mutate in (
                ("missing", lambda c: c.pop("state")),
                ("torn", lambda c: c.pop("integrity_marker")),
                ("tampered", lambda c: c["state"].__setitem__("remaining_volume", Decimal("0.1"))),
                ("time changed", lambda c: c.__setitem__("captured_at_utc", 1040)),
                ("age changed", lambda c: c.__setitem__("max_age_seconds", 9999)),
                ("sequence changed", lambda c: c.__setitem__("checkpoint_sequence", 8)),
                ("audit anchor changed", lambda c: c.__setitem__("audit_sequence", 2)),
                ("old schema", lambda c: c.__setitem__("schema_version", "pending-order-checkpoint-v1.0.0"))):
            with self.subTest(label=label):
                c = deepcopy(base)
                mutate(c)
                restored, _, ok, reason = restore(None, c, DATA["expected_identity"], 1060)
                self.assertFalse(ok)
                self.assertEqual(reason, "PENDING_CHECKPOINT_REJECTED")
                self.assertEqual(restored["status"], "PENDING_RACE_UNKNOWN")
                self.assertTrue(restored["new_entries_blocked"])
        restored, _, ok, _ = restore(None, "malformed", DATA["expected_identity"], 1060)
        self.assertFalse(ok)
        self.assertTrue(restored["new_entries_blocked"])

    def test_signed_but_inconsistent_volume_or_future_event_rejected(self):
        for key, value in (("remaining_volume", Decimal("0.2")),
                           ("last_event_at_utc", 1060)):
            with self.subTest(key=key):
                c = checkpoint()
                c["state"][key] = value
                c["fingerprint"] = fingerprint(c)
                restored, _, ok, _ = restore(None, c, DATA["expected_identity"], 1060)
                self.assertFalse(ok)
                self.assertTrue(restored["new_entries_blocked"])

    def test_wrong_identity_or_stale_checkpoint_rejected(self):
        base = checkpoint()
        for key in DATA["expected_identity"]:
            with self.subTest(key=key):
                identity = dict(DATA["expected_identity"], **{key: "wrong"})
                self.assertFalse(restore(None, base, identity, 1060)[2])
        self.assertFalse(restore(None, base, DATA["expected_identity"], 1351)[2])

    def test_replay_is_idempotent_and_sequence_regression_blocks(self):
        c = checkpoint()
        state, guard, ok, _ = restore(None, c, DATA["expected_identity"], 1060)
        self.assertTrue(ok)
        same, same_guard, ok, reason = restore(state, c, DATA["expected_identity"], 1061, guard)
        self.assertTrue(ok)
        self.assertEqual(reason, "PENDING_CHECKPOINT_REPLAY_IGNORED")
        self.assertEqual(same, state)
        self.assertEqual(same_guard, guard)
        older = deepcopy(c)
        older["checkpoint_sequence"] = 6
        older["fingerprint"] = fingerprint(older)
        rejected, _, ok, reason = restore(state, older, DATA["expected_identity"], 1061, guard)
        self.assertFalse(ok)
        self.assertEqual(reason, "PENDING_CHECKPOINT_SEQUENCE_REGRESSION")
        self.assertEqual(rejected["remaining_risk_reservation_money"], Decimal("36.9"))
        self.assertTrue(rejected["new_entries_blocked"])

    def test_valid_terminal_checkpoint_still_requires_broker_reconciliation(self):
        state, ok = apply_broker_event(initialize(SEED["seed"], 1001),
                                       event("EXPIRE_CONFIRMED", 1, 1500,
                                             confirmed_remaining_volume=0.3))
        self.assertTrue(ok)
        c = make_checkpoint(state, 8, 1501, 300, DATA["audit_anchor"])
        restored, _, ok, _ = restore(None, c, DATA["expected_identity"], 1502)
        self.assertTrue(ok)
        self.assertEqual(restored["cancelled_volume"], Decimal("0.3"))
        self.assertEqual(restored["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(restored["new_entries_blocked"])

    def test_verified_audit_tail_matches_checkpoint_without_unblocking_entry(self):
        state = initialize(SEED["seed"], 1001)
        before = deepcopy(state)
        before.update(initialized=False, status="UNKNOWN", reason_code="ATTESTED_PENDING_SEED_REQUIRED",
                      requested_volume=Decimal(0), filled_volume=Decimal(0),
                      cancelled_volume=Decimal(0), remaining_volume=Decimal(0),
                      filled_initial_risk_money=Decimal(0),
                      remaining_risk_reservation_money=Decimal(0),
                      total_committed_risk_money=Decimal(0), effective_expires_at_utc=0)
        tail = make_record(before, state, "SEED_ACCEPTED", 1, "", "seed-audit-1",
                           1000, 1001, "seed-source-1")
        _, audit_cursor, ok = accept(before, state, tail, cursor_defaults())
        self.assertTrue(ok)
        anchor = dict(audit_sequence=audit_cursor["last_sequence"],
                      audit_fingerprint=audit_cursor["last_fingerprint"],
                      audit_event_id=audit_cursor["last_event_id"],
                      audit_observed_at_utc=audit_cursor["last_observed_at_utc"])
        c = make_checkpoint(state, 7, 1050, 300, anchor)
        restored, guard, ok, _ = restore(None, c, DATA["expected_identity"], 1060)
        self.assertTrue(ok)
        self.assertFalse(guard["audit_tail_verified"])
        matched, guard, ok, reason = verify_audit_tail(restored, c, tail, guard)
        self.assertTrue(ok)
        self.assertEqual(reason, "PENDING_CHECKPOINT_AUDIT_TAIL_MATCHED_BROKER_RECONCILIATION_REQUIRED")
        self.assertTrue(guard["audit_tail_verified"])
        self.assertEqual(matched["status"], "PENDING_RACE_UNKNOWN")
        self.assertTrue(matched["new_entries_blocked"])
        wrong = dict(tail, order_ticket="foreign-ticket")
        wrong["fingerprint"] = audit_fingerprint(wrong)
        rejected, guard, ok, _ = verify_audit_tail(matched, c, wrong, guard)
        self.assertFalse(ok)
        self.assertFalse(guard["audit_tail_verified"])
        self.assertTrue(rejected["new_entries_blocked"])

        changed_anchor = deepcopy(c)
        changed_anchor["audit_fingerprint"] = "another-audit-tail"
        changed_anchor["fingerprint"] = fingerprint(changed_anchor)
        restored, guard, ok, _ = restore(None, changed_anchor, DATA["expected_identity"], 1060)
        self.assertTrue(ok)
        rejected, guard, ok, _ = verify_audit_tail(restored, changed_anchor, tail, guard)
        self.assertFalse(ok)
        self.assertFalse(guard["audit_tail_verified"])
        self.assertTrue(rejected["new_entries_blocked"])

    def test_source_remains_offline(self):
        source = (ROOT / "Storage/PendingOrderCheckpoint.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_RestorePendingOrderCheckpoint", source)
        for forbidden in ("OrderSend(", "FileOpen(", "HistorySelect(", "WebRequest("):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("PendingOrderCheckpoint.mqh", shell)


if __name__ == "__main__":
    unittest.main()
