"""S04 Failed Break v1 (G9, TC-S04-01..10). Synthetic bars and a reference oracle;
this is not MQL5 runtime proof."""
from __future__ import annotations

import unittest
from pathlib import Path

import s04_oracle as s04

ROOT = Path(__file__).resolve().parents[1]
ZL, ZH, ATR = 1.1000, 1.1010, 0.0020


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


def bar(o, h, l, c, atr=ATR):
    return {"open": o, "high": h, "low": l, "close": c, "atr": atr}


def run(bars, profile="SCALP"):
    e = s04.Engine(s04.config(profile))
    states = [e.step(b, ZL, ZH) for b in bars]
    return e, states


BREAK_UP = bar(1.1008, 1.1040, 1.1006, 1.1036)          # closes 0.0026 above zone (>0.10 ATR), body 0.85
BACK_IN = bar(1.1034, 1.1042, 1.1004, 1.1008)          # closes back inside the zone
TRIGGER_DOWN = bar(1.1008, 1.1010, 1.0990, 1.0992)     # bearish, body 0.8, below BACK_IN low - 0.05 ATR


class EngineTests(unittest.TestCase):
    def test_tc_s04_01_wick_alone_creates_no_attempt(self):  # TC-005
        e, states = run([bar(1.1005, 1.1045, 1.1003, 1.1008)])
        self.assertEqual(states, ["IDLE"])

    def test_tc_s04_02_full_short_sequence(self):
        e, states = run([BREAK_UP, BACK_IN, TRIGGER_DOWN])
        self.assertEqual(states, ["BREAK_ATTEMPT", "RETURNED", "TRIGGERED"])
        self.assertEqual(e.direction, -1)
        self.assertAlmostEqual(e.extreme, 1.1042)          # failed-break extreme includes the return bar wick

    def test_mirror_long_after_failed_downside_break(self):
        down = bar(1.1002, 1.1004, 1.0970, 1.0974)
        back = bar(1.0976, 1.1006, 1.0968, 1.1002)
        trig = bar(1.1002, 1.1020, 1.1000, 1.1018)
        e, states = run([down, back, trig])
        self.assertEqual(states, ["BREAK_ATTEMPT", "RETURNED", "TRIGGERED"])
        self.assertEqual(e.direction, 1)

    def test_tc_s04_03_two_closes_beyond_is_accepted(self):
        hold = bar(1.1036, 1.1044, 1.1030, 1.1040)
        e, states = run([BREAK_UP, hold, hold])
        self.assertEqual(states[-1], "INVALIDATED")
        self.assertEqual(e.reason, "BREAK_ACCEPTED")

    def test_tc_s04_04_close_beyond_extreme_invalidates(self):
        surge = bar(1.1010, 1.1080, 1.1008, 1.1075)        # above 1.1042 + 0.10 ATR
        e, states = run([BREAK_UP, BACK_IN, surge])
        self.assertEqual((states[-1], e.reason), ("INVALIDATED", "THESIS_INVALIDATED"))

    def test_tc_s04_05_trigger_window_expires(self):
        idle = bar(1.1006, 1.1009, 1.1003, 1.1005)
        e, states = run([BREAK_UP, BACK_IN, idle, idle, idle])
        self.assertEqual((states[-1], e.reason), ("EXPIRED", "TRIGGER_EXPIRED"))

    def test_weak_break_body_is_ignored(self):
        doji = bar(1.1030, 1.1045, 1.1005, 1.1036)          # body 0.15 of range
        e, states = run([doji])
        self.assertEqual(states, ["IDLE"])

    def test_tc_s04_06_plan_stop_and_target(self):  # TC-006
        p = s04.plan(-1, 1.1042, ATR, 0.0001, 1.0992, (ZL, ZH), [1.0985, 1.0935, 1.0900])
        self.assertAlmostEqual(p["stop"], 1.1042 + 0.0002)
        self.assertEqual(p["target"], 1.0935)               # 1.0985 is less than 1R away
        self.assertIsNone(s04.plan(-1, 1.1042, ATR, 0.0001, 1.0992, (ZL, ZH), [1.1050, 1.0985]))


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.fb = read("Setups/FailedBreak.mqh")
        self.rt = read("Runtime/StrategyCandidateRuntime.mqh")
        self.cl = read("Integration/ControlledLiveRuntime.mqh")

    def test_engine_mirrors_oracle(self):
        cfg = section(self.fb, "void EEA_S04V1Config")
        for token in ("c.break_buffer_atr=0.10", "c.break_body_ratio=0.50", "c.max_bars_to_accept=3",
                      "c.max_bars_for_reaction=3", "c.trigger_body_ratio=0.40", "c.trigger_progress_atr=0.05",
                      "c.invalidation_buffer_atr=0.10", "c.candidate_ttl_bars=2"):
            self.assertIn(token, cfg)
        self.assertIn("#define EEA_S04_ACCEPT_CLOSES 2", self.fb)
        body = section(self.fb, "bool EEA_S04ProcessClosedBarZone", "\n  }\n\n#endif")
        for reason in ("THESIS_INVALIDATED", "CLOSED_BACK_INSIDE_ZONE", "BREAK_ACCEPTED", "NO_RETURN_INSIDE",
                       "FAILED_BREAK_REJECTION_CONFIRMED", "TRIGGER_EXPIRED", "CANDIDATE_TTL_REACHED"):
            self.assertIn('"' + reason + '"', body)
        self.assertIn('"S04-%s-%s-%s-%I64d"', self.fb)
        self.assertIn("e.direction=-break_dir;", self.fb)   # S04 trades against the attempted break

    def test_runtime_runs_s04_beside_s02(self):
        self.assertIn('#include "../Setups/FailedBreak.mqh"', self.rt)
        self.assertIn("EEA_S04ProcessClosedBarZone(engine,bar", self.rt)
        self.assertIn('"_s04"', self.rt)                    # own checkpoint (TC-S04-08)
        self.assertIn("#define EEA_STRATEGY_RUNTIME_MAX_ENGINES 128", self.rt)

    def test_tc_s04_07_opposite_setup_blocks(self):
        self.assertIn('"OPPOSITE_SETUP_ACTIVE"', self.cl)
        on_timer = section(self.cl, "bool EEA_ControlledLiveOnTimer")
        self.assertIn("EEA_ControlledLiveOppositeActive(", on_timer)

    def test_tc_s04_09_shadow_never_submits(self):
        on_timer = section(self.cl, "bool EEA_ControlledLiveOnTimer")
        self.assertIn("strategy.s04_mode!=EEA_S04_MODE_LIVE", on_timer)
        shadow = section(self.cl, "void EEA_S04ShadowOnTimer")
        self.assertNotIn("EEA_ExecutionSubmit", shadow)
        self.assertIn('"S04_SHADOW_CANDIDATE"', shadow)

    def test_s04_never_uses_limit_and_target_beyond_far_edge(self):
        select = section(self.cl, "int EEA_S02SelectEntryMode")
        self.assertIn('strategy.setup[index]!="S04"', select)
        plan = section(self.cl, "bool EEA_ControlledLiveResolveV1Plan")
        self.assertIn("far_edge", plan)

    def test_tc_s04_10_replay_is_deterministic_and_measure_only(self):
        rp = read("Runtime/SetupReplay.mqh")
        self.assertNotIn("EEA_ExecutionSubmit", rp)
        self.assertNotIn("OrderSend", rp)
        self.assertNotIn("TimeGMT()", section(rp, "bool EEA_SetupReplayEvaluate"))


if __name__ == "__main__":
    unittest.main()
