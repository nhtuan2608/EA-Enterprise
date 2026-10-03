"""S02 v1 design checks (docs/superpowers/specs/2026-10-03-s02-break-retest-v1-design.md).

Synthetic bars and a reference oracle; this is not MQL5 runtime proof.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import s02_oracle
import s02_v1_oracle as v1

ROOT = Path(__file__).resolve().parents[1]
H = 3600
DAY = 86400
MONDAY = 1791158400  # 2026-10-05 00:00 server time, a Monday


def bar(t, o, h, l, c):
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def flat_bars(start, count, step, price, spread=0.0005):
    return [bar(start + i * step, price, price + spread, price - spread, price) for i in range(count)]


class RiskLimitsTests(unittest.TestCase):
    def test_limits_follow_firm_floors(self):
        two = v1.risk_limits("FTMO_2_STEP")
        one = v1.risk_limits("FTMO_1_STEP")
        self.assertAlmostEqual(two["internal_daily"], 0.02)
        self.assertAlmostEqual(two["per_trade"], 0.005)
        self.assertAlmostEqual(two["total_open"], 0.02)
        self.assertAlmostEqual(two["currency_exposure"], 0.0125)
        self.assertAlmostEqual(two["internal_weekly"], 0.04)
        self.assertAlmostEqual(one["internal_daily"], 0.012)
        self.assertAlmostEqual(one["per_trade"], 0.003)
        self.assertAlmostEqual(one["currency_exposure"], 0.0075)
        self.assertAlmostEqual(one["internal_weekly"], 0.024)
        for limits in (one, two):
            self.assertLess(limits["internal_daily"], limits["firm_daily"])
            self.assertLess(limits["internal_weekly"], limits["firm_overall"])
            self.assertLessEqual(limits["total_open"], limits["internal_daily"])
        self.assertIsNone(v1.risk_limits("UNSELECTED"))

    def test_trade_risk_money_never_exceeds_cap_and_modifiers_only_reduce(self):
        limits = v1.risk_limits("FTMO_2_STEP")
        self.assertAlmostEqual(v1.trade_risk_money(limits, 105_000, 100_000, 1.0), 500.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 95_000, 100_000, 1.0), 475.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 100_000, 100_000, 0.5), 250.0)
        self.assertAlmostEqual(v1.trade_risk_money(limits, 100_000, 100_000, 3.0), 500.0)

    def test_mql_formulas_match_oracle(self):
        src = (ROOT / "Risk/RiskLimitsProfile.mqh").read_text(encoding="utf-8")
        for token in ("MathMin(0.4*l.firm_daily_fraction,0.02)", "l.internal_daily_fraction/4.0",
                      "l.total_open_fraction=l.internal_daily_fraction", "2.5*l.per_trade_fraction",
                      "MathMin(2.0*l.internal_daily_fraction,0.4*l.firm_overall_fraction)",
                      "l.safety_buffer_fraction=l.per_trade_fraction", "MathMax(0.0,MathMin(1.0,modifier))",
                      "RISK_LIMITS_POLICY_UNSELECTED", "EEA_FtmoPolicyRates"):
            self.assertIn(token, src)


class LocationTests(unittest.TestCase):
    def test_tc_s02_01_two_independent_sources_qualify_one_does_not(self):
        points = [("PREV_DAY", "HIGH", 1.10000, 100), ("SWING", "HIGH", 1.10020, 200), ("SESSION", "HIGH", 1.12000, 300)]
        zones = v1.build_zones(points, tolerance=0.0005, max_width=0.0010)
        self.assertEqual(len(zones), 2)
        self.assertTrue(zones[0]["qualified"])
        self.assertEqual(zones[0]["sources"], "PREV_DAY+SWING")
        self.assertFalse(zones[1]["qualified"])
        self.assertEqual(zones[1]["reason"], "CONFLUENCE_INSUFFICIENT")

    def test_tc_s02_02_same_bar_counts_once(self):
        points = [("PREV_DAY", "HIGH", 1.10000, 500), ("SESSION", "HIGH", 1.10000, 500)]
        zone = v1.build_zones(points, tolerance=0.0005, max_width=0.0010)[0]
        self.assertEqual(zone["independent_sources"], 1)
        self.assertFalse(zone["qualified"])

    def test_tc_s02_03_atr_scaled_tolerance_is_symbol_independent(self):
        base = [("PREV_DAY", "LOW", 1.0, 1), ("SWING", "LOW", 1.0015, 2), ("SESSION", "LOW", 1.006, 3)]
        expected = None
        for scale, atr in ((1.0, 0.008), (2600.0, 0.008 * 2600.0), (60000.0, 0.008 * 60000.0)):
            points = [(s, side, p * scale, t) for s, side, p, t in base]
            zones = v1.build_zones(points, tolerance=0.25 * atr, max_width=0.5 * atr)
            shape = [(z["members"], z["qualified"], z["sources"]) for z in zones]
            expected = expected or shape
            self.assertEqual(shape, expected)

    def test_zone_wider_than_limit_is_rejected(self):
        points = [("PREV_DAY", "HIGH", 1.1000, 1), ("SWING", "HIGH", 1.1004, 2), ("SESSION", "HIGH", 1.1008, 3)]
        zone = v1.build_zones(points, tolerance=0.0005, max_width=0.0006)[0]
        self.assertEqual(zone["reason"], "ZONE_TOO_WIDE")

    def test_previous_day_week_and_session_windows(self):
        now = MONDAY + 2 * DAY + 10 * H  # Wednesday 10:00
        bars = flat_bars(MONDAY - 7 * DAY, 10 * 24, H, 1.1)
        bars[24 * 8 + 5]["high"] = 1.2   # Tuesday 05:00 -> previous day high
        bars[3]["low"] = 1.0             # previous week Monday 03:00 -> previous week low
        day = v1.levels_previous_day(bars, now)
        self.assertEqual(day[0][2:], (1.2, MONDAY + DAY + 5 * H))
        week = v1.levels_previous_week(bars, now)
        self.assertEqual(week[1][2:], (1.0, MONDAY - 7 * DAY + 3 * H))
        self.assertEqual(v1.week_start(now), MONDAY)
        # server is UTC+3; London 07-12 UTC is 10-15 server time. At 10:00 server the
        # session of today has not ended, so yesterday's window is used.
        session = v1.levels_session(bars, now, 3 * H, 7, 12)
        self.assertGreaterEqual(session[0][3], MONDAY + DAY + 10 * H)
        self.assertLess(session[0][3], MONDAY + DAY + 15 * H)

    def test_swings_must_be_confirmed_and_unbroken(self):
        bars = flat_bars(0, 20, H, 1.0)
        bars[10] = bar(10 * H, 1.0, 1.05, 0.999, 1.0)
        swings = v1.levels_swings(bars, wing=3, lookback=20)
        self.assertIn(("SWING", "HIGH", 1.05, 10 * H), swings)
        bars[15]["close"] = 1.06
        bars[15]["high"] = 1.06
        self.assertNotIn(("SWING", "HIGH", 1.05, 10 * H), v1.levels_swings(bars, wing=3, lookback=20))

    def test_mql_location_contract(self):
        src = (ROOT / "Market/ConfluenceLevels.mqh").read_text(encoding="utf-8")
        for token in ("EEA_BuildConfluenceZones", "CONFLUENCE_INSUFFICIENT", "ZONE_TOO_WIDE", "CONFLUENCE_ZONE",
                      "used_times[u]==points[order[n]].bar_time", "EEA_LevelsPreviousDay", "EEA_LevelsPreviousWeek",
                      "EEA_LevelsSession", "EEA_LevelsSwings", "(day+3)%7"):
            self.assertIn(token, src)
        self.assertNotIn("CopyRates", src)
        self.assertNotIn("OrderSend", src)


class HtfTests(unittest.TestCase):
    def _zigzag(self, rising: bool):
        bars, price = [], 1.0
        for leg in range(6):
            for k in range(5):
                step = 0.002 if (leg % 2 == 0) == rising else -0.002
                drift = 0.001 if rising else -0.001
                price += step + drift
                bars.append(bar(len(bars) * H, price, price + 0.0005, price - 0.0005, price))
        return bars

    def test_tc_s02_06_structure_and_counter_trend_modifier(self):
        self.assertEqual(v1.htf_structure(self._zigzag(True), 2), "UP")
        self.assertEqual(v1.htf_structure(self._zigzag(False), 2), "DOWN")
        self.assertEqual(v1.htf_structure(flat_bars(0, 30, H, 1.0), 2), "NEUTRAL")
        self.assertEqual(v1.htf_risk_modifier("UP", -1), 0.5)
        self.assertEqual(v1.htf_risk_modifier("DOWN", 1), 0.5)
        self.assertEqual(v1.htf_risk_modifier("UP", 1), 1.0)
        self.assertEqual(v1.htf_risk_modifier("NEUTRAL", -1), 1.0)
        src = (ROOT / "Market/ConfluenceLevels.mqh").read_text(encoding="utf-8")
        self.assertIn('if(highs[0]>highs[1] && lows[0]>lows[1]) return "UP";', src)


class ZoneEngineTests(unittest.TestCase):
    CONFIG = {"config_version": "s02-v1-scalp-0.1.0", "break_buffer_atr": 0.10, "acceptance_buffer_atr": 0.0,
              "retest_tolerance_atr": 0.15, "invalidation_buffer_atr": 0.10, "hold_buffer_atr": 0.0,
              "max_bars_to_accept": 2, "max_bars_to_retest": 12, "max_bars_for_reaction": 3,
              "candidate_ttl_bars": 2, "break_body_ratio": 0.5, "trigger_body_ratio": 0.4,
              "trigger_progress_atr": 0.05, "fail_on_close_inside_zone": True}

    def run_bars(self, bars, low=1.1000, high=1.1010, atr=0.0020):
        engine = s02_oracle.new_engine({"canonical_symbol": "EURUSD", "timeframe": "M5"}, self.CONFIG)
        events = [s02_oracle.process_zone(engine, dict(b, atr=atr), low, high, self.CONFIG) for b in bars]
        return engine, events

    def test_tc_s02_04_full_long_sequence_tracks_zone_and_retest_extreme(self):
        bars = [bar(300, 1.1008, 1.1045, 1.1006, 1.1040),   # strong break above zone high
                bar(600, 1.1040, 1.1050, 1.1030, 1.1045),   # acceptance
                bar(900, 1.1045, 1.1046, 1.1012, 1.1020),   # retest touches zone high + tol
                bar(1200, 1.1020, 1.1060, 1.1018, 1.1055)]  # trigger
        engine, events = self.run_bars(bars)
        self.assertEqual([e["state"] for e in events], ["DETECTED", "ARMED", "RETESTING", "TRIGGERED"])
        self.assertAlmostEqual(engine["invalidation_price"], 1.1000 - 0.1 * 0.0020)
        self.assertAlmostEqual(engine["candidate"]["retest_extreme"], 1.1012)
        self.assertEqual(engine["candidate"]["zone_high"], 1.1010)

    def test_tc_s02_05_close_back_inside_fails_acceptance_and_weak_break_is_ignored(self):
        _, events = self.run_bars([bar(300, 1.1008, 1.1045, 1.1006, 1.1040), bar(600, 1.1040, 1.1041, 1.1003, 1.1005)])
        self.assertEqual(events[-1]["reason"], "ACCEPTANCE_FAILED")
        weak = bar(300, 1.1030, 1.1060, 1.1000, 1.1036)  # closes beyond but body is 10% of range
        _, events = self.run_bars([weak])
        self.assertEqual(events[0]["state"], "IDLE")

    def test_zero_width_zone_with_v1_extras_off_is_the_prototype(self):
        legacy = dict(self.CONFIG, break_body_ratio=0.0, trigger_body_ratio=0.0,
                      trigger_progress_atr=0.0, fail_on_close_inside_zone=False)
        bars = [bar(300, 1.1008, 1.1045, 1.1006, 1.1040), bar(600, 1.1040, 1.1050, 1.1030, 1.1045)]
        a = s02_oracle.new_engine({"canonical_symbol": "X", "timeframe": "M5"}, legacy)
        b = s02_oracle.new_engine({"canonical_symbol": "X", "timeframe": "M5"}, legacy)
        for item in bars:
            ea = s02_oracle.process(a, dict(item, atr=0.002), 1.1010, legacy)
            eb = s02_oracle.process_zone(b, dict(item, atr=0.002), 1.1010, 1.1010, legacy)
            self.assertEqual((ea["state"], ea["reason"]), (eb["state"], eb["reason"]))

    def test_mql_engine_and_checkpoint_carry_zone(self):
        engine = (ROOT / "Setups/BreakRetest.mqh").read_text(encoding="utf-8")
        for token in ("bool EEA_S02ProcessClosedBarZone", "return EEA_S02ProcessClosedBarZone(e,b,key_level,key_level,c,ev);",
                      "EEA_S02BodyOk(b,1,c.break_body_ratio)", "\"ACCEPTANCE_FAILED\"", "e.retest_extreme=",
                      "void EEA_S02V1Config", "c.max_bars_to_retest=swing ? 10 : 12;", "c.fail_on_close_inside_zone=true;",
                      "e.invalidation_price=zone_low-c.invalidation_buffer_atr*b.atr;"):
            self.assertIn(token, engine)
        store = (ROOT / "Storage/StrategyCandidateStore.mqh").read_text(encoding="utf-8")
        for token in ('\\"zone_low\\":', '\\"retest_extreme\\":',
                      'engine.zone_low=zone_low_text=="" ? engine.key_level', "engine.zone_low>engine.zone_high"):
            self.assertIn(token, store)


if __name__ == "__main__":
    unittest.main()
