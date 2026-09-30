"""Synthetic state-machine tests for the account-wide risk ledger."""
from copy import deepcopy
import json
import unittest
from pathlib import Path

from account_risk_ledger_oracle import apply_snapshot, defaults

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/account-risk-ledger-v0.1.0.json").read_text(encoding="utf-8"))


def snapshot(**overrides):
    return FIXTURE["base_snapshot"] | overrides


class AccountRiskLedgerExamples(unittest.TestCase):
    def test_partial_fill_sl_modify_and_close_keep_risk_measures_separate(self):
        ledger = defaults()
        positions = FIXTURE["partial_fill_positions"]
        orders = FIXTURE["partial_fill_orders"]
        deals = FIXTURE["partial_fill_deals"]
        first = snapshot()
        self.assertTrue(apply_snapshot(ledger, first, positions, orders, deals, 120))
        self.assertEqual(ledger["initial_risk_money"], 70)
        self.assertEqual(ledger["projected_loss_to_sl_money"], 170)
        self.assertEqual(ledger["remaining_loss_to_sl_money"], 144)
        self.assertEqual(ledger["floor_headroom_after_ledger_risk_money"], 356)
        self.assertEqual(ledger["position_count"], 3)
        self.assertEqual(ledger["working_order_count"], 2)
        self.assertFalse(ledger["new_entries_blocked"])

        # Replaying an identical full snapshot is idempotent and cannot double-count.
        before = ledger.copy()
        self.assertTrue(apply_snapshot(ledger, first, positions, orders, deals, 130))
        self.assertEqual(ledger["last_transition"], "DUPLICATE_IGNORED")
        self.assertEqual(ledger["remaining_loss_to_sl_money"], before["remaining_loss_to_sl_money"])

        # SL tightening changes remaining risk only; original entry/intent measures stay frozen.
        modified = snapshot(event_id="snapshot-event-2", source_snapshot_id="account-snap-2",
                            positions_snapshot_id="positions-2", orders_snapshot_id="orders-2",
                            deals_snapshot_id="deals-2", policy_snapshot_id="policy-2",
                            content_fingerprint="sha256:sl-modified",
                            captured_at_utc=200, event_sequence=2)
        self.assertTrue(apply_snapshot(ledger, modified, FIXTURE["sl_modified_positions"], orders, deals, 220))
        self.assertEqual(ledger["initial_risk_money"], 70)
        self.assertEqual(ledger["projected_loss_to_sl_money"], 170)
        self.assertEqual(ledger["remaining_loss_to_sl_money"], 130)
        self.assertEqual(ledger["floating_pnl_after_costs"], 18)

        closed = snapshot(event_id="snapshot-event-3", source_snapshot_id="account-snap-3",
                          positions_snapshot_id="positions-3", orders_snapshot_id="orders-3",
                          deals_snapshot_id="deals-3", policy_snapshot_id="policy-3",
                          content_fingerprint="sha256:closed",
                          captured_at_utc=300, event_sequence=3, deal_watermark=3)
        self.assertTrue(apply_snapshot(ledger, closed, FIXTURE["close_positions"],
                                       FIXTURE["close_orders"], FIXTURE["close_deals"], 320))
        self.assertEqual(ledger["initial_risk_money"], 30)
        self.assertEqual(ledger["projected_loss_to_sl_money"], 70)
        self.assertEqual(ledger["remaining_loss_to_sl_money"], 60)
        self.assertEqual(ledger["position_count"], 2)
        self.assertEqual(ledger["working_order_count"], 1)

    def test_missing_sources_and_reconciliation_fail_closed_but_preserve_protection(self):
        for case in FIXTURE["invalid_snapshot_cases"]:
            with self.subTest(name=case["name"]):
                s = deepcopy(FIXTURE["base_snapshot"])
                if "mutation" in case:
                    key, value = case["mutation"]
                    s[key] = value
                ledger = defaults()
                now = case.get("now_utc", 120)
                self.assertFalse(apply_snapshot(ledger, s, FIXTURE["partial_fill_positions"],
                                                FIXTURE["partial_fill_orders"],
                                                FIXTURE["partial_fill_deals"], now))
                self.assertEqual(ledger["ledger_status"], "POLICY_DATA_UNKNOWN")
                self.assertTrue(ledger["new_entries_blocked"])
                self.assertTrue(ledger["protect_existing_positions"])
                self.assertEqual(ledger["reason_code"], case["expected_reason"])

    def test_out_of_order_conflicting_and_invalid_deal_events_fail_closed(self):
        rows, orders, deals = (FIXTURE["partial_fill_positions"], FIXTURE["partial_fill_orders"],
                               FIXTURE["partial_fill_deals"])
        ledger = defaults()
        self.assertTrue(apply_snapshot(ledger, snapshot(), rows, orders, deals, 120))
        stale = snapshot(event_id="old-event", source_snapshot_id="old-snapshot",
                         content_fingerprint="sha256:stale", captured_at_utc=90, event_sequence=2)
        self.assertFalse(apply_snapshot(ledger, stale, rows, orders, deals, 130))
        self.assertEqual(ledger["reason_code"], "OUT_OF_ORDER_ACCOUNT_SNAPSHOT")
        self.assertTrue(ledger["new_entries_blocked"])
        self.assertEqual(ledger["remaining_loss_to_sl_money"], 144)  # Keep last good risk for protection.

        ledger = defaults()
        self.assertTrue(apply_snapshot(ledger, snapshot(), rows, orders, deals, 120))
        conflict = snapshot(source_snapshot_id="different-content")
        self.assertFalse(apply_snapshot(ledger, conflict, rows, orders, deals, 130))
        self.assertEqual(ledger["reason_code"], "SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT")

        changed_rows = deepcopy(rows)
        changed_rows[0]["initial_risk_money"] += 1
        changed = snapshot()
        changed["content_fingerprint"] = "sha256:changed-row"
        ledger = defaults()
        self.assertTrue(apply_snapshot(ledger, snapshot(), rows, orders, deals, 120))
        self.assertFalse(apply_snapshot(ledger, changed, changed_rows, orders, deals, 130))
        self.assertEqual(ledger["reason_code"], "SNAPSHOT_ID_REUSED_WITH_DIFFERENT_CONTENT")

        invalid_deals = [deals[0], deals[0]]
        ledger = defaults()
        self.assertFalse(apply_snapshot(ledger, snapshot(), rows, orders, invalid_deals, 120))
        self.assertEqual(ledger["reason_code"], "DEAL_HISTORY_INVALID_OR_OUT_OF_ORDER")

    def test_account_mode_and_netting_positions_are_explicit(self):
        s = snapshot(account_mode="NETTING")
        ledger = defaults()
        self.assertTrue(apply_snapshot(ledger, s, FIXTURE["partial_fill_positions"],
                                       FIXTURE["partial_fill_orders"], FIXTURE["partial_fill_deals"], 120))
        duplicate_symbol = deepcopy(FIXTURE["partial_fill_positions"])
        duplicate_symbol.append(duplicate_symbol[0] | {"position_id": "second-net-position"})
        ledger = defaults()
        self.assertFalse(apply_snapshot(ledger, s, duplicate_symbol,
                                        FIXTURE["partial_fill_orders"], FIXTURE["partial_fill_deals"], 120))
        self.assertEqual(ledger["reason_code"], "NETTING_DUPLICATE_SYMBOL_POSITION")

    def test_existing_risk_can_block_new_entries_without_losing_ledger(self):
        ledger = defaults()
        low_headroom = snapshot(equity_floor_headroom_money=100)
        self.assertTrue(apply_snapshot(ledger, low_headroom, FIXTURE["partial_fill_positions"],
                                       FIXTURE["partial_fill_orders"], FIXTURE["partial_fill_deals"], 120))
        self.assertEqual(ledger["ledger_status"], "RECONCILED")
        self.assertTrue(ledger["new_entries_blocked"])
        self.assertTrue(ledger["protect_existing_positions"])
        self.assertEqual(ledger["floor_headroom_after_ledger_risk_money"], -44)

    def test_nonfinite_derived_headroom_is_unknown(self):
        positions = deepcopy(FIXTURE["partial_fill_positions"])
        positions[0]["remaining_loss_to_sl"] = 1e308
        positions[1]["remaining_loss_to_sl"] = 0
        positions[2]["remaining_loss_to_sl"] = 0
        orders = deepcopy(FIXTURE["partial_fill_orders"])
        for row in orders:
            row["remaining_loss_to_sl"] = 0
        ledger = defaults()
        self.assertFalse(apply_snapshot(ledger, snapshot(equity_floor_headroom_money=-1e308),
                                        positions, orders, FIXTURE["partial_fill_deals"], 120))
        self.assertEqual(ledger["reason_code"], "LEDGER_TOTAL_OVERFLOW")
        self.assertTrue(ledger["new_entries_blocked"])

    def test_missing_position_risk_lineage_attestation_is_unknown(self):
        positions = deepcopy(FIXTURE["partial_fill_positions"])
        positions[0]["initial_risk_money"] = 25  # differs from prior entry snapshot
        positions[0]["risk_lineage_valid"] = False
        ledger = defaults()
        self.assertFalse(apply_snapshot(ledger, snapshot(), positions,
                                        FIXTURE["partial_fill_orders"],
                                        FIXTURE["partial_fill_deals"], 120))
        self.assertEqual(ledger["reason_code"], "POSITION_ROW_INVALID")
        self.assertTrue(ledger["new_entries_blocked"])

    def test_duplicate_last_good_snapshot_cannot_clear_unknown_state(self):
        ledger = defaults()
        s = snapshot()
        positions, orders, deals = (FIXTURE["partial_fill_positions"],
                                    FIXTURE["partial_fill_orders"], FIXTURE["partial_fill_deals"])
        self.assertTrue(apply_snapshot(ledger, s, positions, orders, deals, 120))
        broken = snapshot(event_id="bad-event", source_snapshot_id="bad-snapshot",
                          content_fingerprint="sha256:broken", event_sequence=2,
                          captured_at_utc=121, other_ea_activity_included=False)
        self.assertFalse(apply_snapshot(ledger, broken, positions, orders, deals, 130))
        self.assertFalse(apply_snapshot(ledger, s, positions, orders, deals, 130))
        self.assertEqual(ledger["ledger_status"], "POLICY_DATA_UNKNOWN")
        self.assertEqual(ledger["reason_code"], "DUPLICATE_SNAPSHOT_WHILE_LEDGER_UNKNOWN")

    def test_module_has_no_broker_or_order_path_and_is_not_in_shell(self):
        source = (ROOT / "Risk/AccountRiskLedger.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_ApplyLedgerSnapshot", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("CTrade", source)
        self.assertNotIn("PositionGet", source)
        self.assertNotIn("AccountRiskLedger.mqh", shell)


if __name__ == "__main__":
    unittest.main()
