"""Synthetic reset-ledger oracle; UTC timestamps are caller attestations, not timezone code."""
import json
import math
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "Tests/Fixtures/daily-reset-ledger-v0.1.0.json").read_text(encoding="utf-8"))


def new_state(policy):
    return {**policy, "status": "UNKNOWN", "reason_code": "FIRST_RESET_SNAPSHOT_REQUIRED",
            "snapshot_id": "", "prague_day_id": "", "day_index": -1, "reset_at_utc": 0,
            "balance_at_reset": 0, "highest_reset_balance": 0,
            "daily_floor": 0, "overall_floor": 0}


def apply(state, snapshot):
    def reject(reason):
        state["status"], state["reason_code"] = "UNKNOWN", reason
        return False

    if (state["policy_id"] not in ("FTMO_1_STEP", "FTMO_2_STEP") or
            any(snapshot[k] != state[k] for k in ("config_version", "account_epoch_id", "account_currency"))):
        return reject("RESET_POLICY_OR_EPOCH_MISMATCH")
    if (not snapshot["snapshot_id"] or not snapshot["prague_day_id"] or
            snapshot["day_index"] < 0 or snapshot["reset_at_utc"] <= 0 or
            not snapshot["prague_midnight_confirmed"] or snapshot["data_quality"] != "OK" or
            not math.isfinite(snapshot["balance_at_reset"])):
        return reject("RESET_SNAPSHOT_MISSING_OR_UNTRUSTED")
    if state["day_index"] == snapshot["day_index"]:
        if all(state[k] == snapshot[k] for k in ("snapshot_id", "prague_day_id", "reset_at_utc", "balance_at_reset")):
            state["reason_code"] = "DUPLICATE_RESET_IGNORED"
            return state["status"] == "OK"
        return reject("CONFLICTING_RESET_SNAPSHOT")
    if (snapshot["day_index"] != state["day_index"] + 1 or
            (state["day_index"] >= 0 and
             (snapshot["reset_at_utc"] <= state["reset_at_utc"] or
              snapshot["prague_day_id"] <= state["prague_day_id"]))):
        return reject("RESET_SEQUENCE_GAP_OR_OUT_OF_ORDER")
    if state["day_index"] == -1 and snapshot["balance_at_reset"] != state["initial_capital"]:
        return reject("FIRST_DAY_BALANCE_NOT_INITIAL")

    initial = state["initial_capital"]
    high = initial if state["day_index"] == -1 else state["highest_reset_balance"]
    if state["policy_id"] == "FTMO_1_STEP":
        high = max(high, snapshot["balance_at_reset"])
    daily_rate = 0.03 if state["policy_id"] == "FTMO_1_STEP" else 0.05
    daily = snapshot["balance_at_reset"] - initial * daily_rate
    overall = (high if state["policy_id"] == "FTMO_1_STEP" else initial) - initial * 0.10
    if not all(math.isfinite(x) for x in (high, daily, overall)):
        return reject("RESET_FLOOR_CALCULATION_INVALID")
    state.update({k: snapshot[k] for k in ("snapshot_id", "prague_day_id", "day_index", "reset_at_utc", "balance_at_reset")})
    state.update(highest_reset_balance=high, daily_floor=daily, overall_floor=overall,
                 status="OK", reason_code="RESET_FLOORS_CALCULATED")
    return True


class DailyResetLedgerExamples(unittest.TestCase):
    def test_one_step_trailing_floor_and_spring_boundary(self):
        case = FIXTURE["one_step"]
        state = new_state(case["policy"])
        daily, overall = [], []
        for snapshot in case["snapshots"]:
            self.assertTrue(apply(state, snapshot))
            daily.append(state["daily_floor"])
            overall.append(state["overall_floor"])
        self.assertEqual(daily, case["expected_daily_floors"])
        self.assertEqual(overall, case["expected_overall_floors"])
        self.assertEqual(case["snapshots"][1]["reset_at_utc"] - case["snapshots"][0]["reset_at_utc"], 23 * 3600)

    def test_two_step_static_floor_and_fall_boundary(self):
        case = FIXTURE["two_step"]
        state = new_state(case["policy"])
        daily, overall = [], []
        for snapshot in case["snapshots"]:
            self.assertTrue(apply(state, snapshot))
            daily.append(state["daily_floor"])
            overall.append(state["overall_floor"])
        self.assertEqual(daily, case["expected_daily_floors"])
        self.assertEqual(overall, case["expected_overall_floors"])
        self.assertEqual(case["snapshots"][1]["reset_at_utc"] - case["snapshots"][0]["reset_at_utc"], 25 * 3600)

    def test_missing_day_and_conflicting_duplicate_fail_closed(self):
        case = FIXTURE["one_step"]
        state = new_state(case["policy"])
        self.assertTrue(apply(state, case["snapshots"][0]))
        self.assertFalse(apply(state, case["snapshots"][2]))
        self.assertEqual(state["status"], "UNKNOWN")
        self.assertEqual(state["day_index"], 0)
        self.assertTrue(apply(state, case["snapshots"][1]))
        self.assertTrue(apply(state, case["snapshots"][1]))
        conflicting = deepcopy(case["snapshots"][1])
        conflicting["balance_at_reset"] += 1
        self.assertFalse(apply(state, conflicting))
        self.assertEqual(state["reason_code"], "CONFLICTING_RESET_SNAPSHOT")

    def test_first_day_balance_and_account_epoch_must_match(self):
        case = FIXTURE["one_step"]
        wrong_balance = deepcopy(case["snapshots"][0])
        wrong_balance["balance_at_reset"] += 1
        state = new_state(case["policy"])
        self.assertFalse(apply(state, wrong_balance))
        self.assertEqual(state["reason_code"], "FIRST_DAY_BALANCE_NOT_INITIAL")
        wrong_epoch = deepcopy(case["snapshots"][0])
        wrong_epoch["account_epoch_id"] = "another-account"
        self.assertFalse(apply(state, wrong_epoch))
        self.assertEqual(state["reason_code"], "RESET_POLICY_OR_EPOCH_MISMATCH")

    def test_module_is_isolated_and_has_no_clock_or_order_path(self):
        source = (ROOT / "Risk/DailyResetLedger.mqh").read_text(encoding="utf-8")
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        self.assertIn("EEA_DailyResetApply", source)
        self.assertNotIn("TimeGMT(", source)
        self.assertNotIn("OrderSend", source)
        self.assertNotIn("DailyResetLedger.mqh", shell)


if __name__ == "__main__":
    unittest.main()
