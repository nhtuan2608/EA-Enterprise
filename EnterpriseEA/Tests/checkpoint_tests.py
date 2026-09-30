"""Fixed offline restart/persistence contract cases."""
from copy import deepcopy
import json
import unittest
from pathlib import Path

from checkpoint_oracle import defaults, fingerprint, reattest_daily, restore

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/ledger-checkpoint-v1.0.0.json").read_text(encoding="utf-8"))
BASE = FIXTURE["checkpoint"]
IDENTITY = FIXTURE["expected_identity"]


def resign(checkpoint):
    checkpoint["fingerprint"] = fingerprint(checkpoint["payload"])


class LedgerCheckpointExamples(unittest.TestCase):
    def test_clean_restart_restores_daily_and_account_risk_state(self):
        state = defaults()
        ok, result = restore(state, deepcopy(BASE), IDENTITY, 550)
        self.assertTrue(ok)
        self.assertEqual(result, "CHECKPOINT_RESTORED_PENDING_RESET_AND_BROKER_RECONCILIATION")
        self.assertEqual(state["daily_status"], "UNKNOWN")
        self.assertEqual(state["risk_status"], "POLICY_DATA_UNKNOWN")
        self.assertEqual(state["daily"]["overall_floor"], 9300)
        self.assertEqual(state["risk"]["initial_risk_money"], 180)
        self.assertEqual(state["risk"]["remaining_loss_to_sl_money"], 120)
        self.assertTrue(state["new_entries_blocked"])
        self.assertTrue(state["protect_existing_positions"])

    def test_torn_missing_or_tampered_payload_fails_closed(self):
        for label, mutate in (
                ("missing", lambda c: c["payload"].pop("risk_source_snapshot_id")),
                ("torn", lambda c: c.pop("integrity_marker")),
                ("tampered", lambda c: c["payload"].__setitem__("remaining_loss_to_sl_money", 999))):
            with self.subTest(label=label):
                c = deepcopy(BASE)
                mutate(c)
                state = defaults()
                ok, result = restore(state, c, IDENTITY, 550)
                self.assertFalse(ok)
                self.assertEqual(result, "CHECKPOINT_REJECTED")
                self.assertEqual(state["daily_status"], "UNKNOWN")
                self.assertEqual(state["risk_status"], "POLICY_DATA_UNKNOWN")
                self.assertTrue(state["new_entries_blocked"])
                self.assertTrue(state["protect_existing_positions"])

    def test_config_account_epoch_or_identity_mismatch_fails_closed(self):
        for key, value in (("config_version", "other-config"), ("account_epoch_id", "new-epoch"),
                           ("account_id", "other-account"), ("broker_server", "other-server"),
                           ("account_currency", "EUR")):
            with self.subTest(key=key):
                state = defaults()
                self.assertFalse(restore(state, deepcopy(BASE), IDENTITY | {key: value}, 550)[0])
                self.assertEqual(state["risk_status"], "POLICY_DATA_UNKNOWN")

    def test_stale_checkpoint_is_rejected(self):
        state = defaults()
        self.assertFalse(restore(state, deepcopy(BASE), IDENTITY, 801)[0])
        self.assertTrue(state["new_entries_blocked"])

    def test_same_day_reattest_needs_fresh_matching_reset_evidence(self):
        state = defaults()
        self.assertTrue(restore(state, deepcopy(BASE), IDENTITY, 550)[0])
        p = BASE["payload"]
        fresh = {k: p[k] for k in ("config_version", "account_epoch_id", "account_currency",
                                    "prague_day_id", "day_index", "reset_at_utc", "balance_at_reset")}
        fresh.update(snapshot_id=p["daily_snapshot_id"], prague_midnight_confirmed=True,
                     data_quality="OK")
        self.assertFalse(reattest_daily(state, fresh, "2026-10-01"))
        self.assertEqual(state["daily_status"], "UNKNOWN")
        self.assertTrue(reattest_daily(state, fresh, "2026-09-30"))
        self.assertEqual(state["daily_status"], "OK")
        self.assertEqual(state["risk_status"], "POLICY_DATA_UNKNOWN")
        self.assertTrue(state["new_entries_blocked"])

    def test_invalid_checkpoint_cannot_be_reattested_into_daily_ok(self):
        state = defaults()
        invalid = deepcopy(BASE)
        invalid.pop("integrity_marker")
        self.assertFalse(restore(state, invalid, IDENTITY, 550)[0])
        self.assertFalse(reattest_daily(state, {}, "2026-09-30"))
        self.assertEqual(state["daily_status"], "UNKNOWN")

    def test_replay_is_idempotent_and_sequence_regression_rejected(self):
        state = defaults()
        self.assertTrue(restore(state, deepcopy(BASE), IDENTITY, 550)[0])
        before = deepcopy(state)
        ok, result = restore(state, deepcopy(BASE), IDENTITY, 560)
        self.assertTrue(ok)
        self.assertEqual(result, "CHECKPOINT_REPLAY_IGNORED")
        self.assertEqual(state, before)

        older = deepcopy(BASE)
        older["payload"]["checkpoint_sequence"] -= 1
        resign(older)
        self.assertFalse(restore(state, older, IDENTITY, 560)[0])
        self.assertTrue(state["new_entries_blocked"])

    def test_checkpoint_module_is_offline_and_not_in_shell(self):
        source = (ROOT / "Storage/LedgerCheckpoint.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_RestoreLedgerCheckpoint", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("LedgerCheckpoint.mqh", shell)


if __name__ == "__main__":
    unittest.main()
