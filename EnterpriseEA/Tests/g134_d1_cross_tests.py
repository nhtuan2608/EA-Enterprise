"""G134: the D1 golden/death cross weight for S07 (EnterpriseEA + S07Tester) - wiring and the D1 state rule.

  python -m pytest -q Tests/g134_d1_cross_tests.py
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_inputs_default_off():
    ea = src("EnterpriseEA.mq5")
    assert re.search(r"input double InpS07D1CrossWeight\s*=\s*1\.0;", ea)
    assert "g_s07_d1_cross_weight=InpS07D1CrossWeight;" in ea
    tester = src("S07Tester.mq5")
    assert re.search(r"input double InpD1CrossWeight\s*=\s*1\.0;", tester)


def test_weight_applies_only_against_the_state_and_only_when_enabled():
    live = src("Integration/ControlledLiveRuntime.mqh")
    assert "if(s07 && g_s07_d1_cross_weight<1.0 && EEA_S07D1CrossState(symbol.broker_symbol)==-direction)" in live
    tester = src("S07Tester.mq5")
    assert "if(InpD1CrossWeight<1.0 && D1CrossState()==-dir)" in tester


def test_state_uses_closed_d1_bars():
    for rel, name in (("Risk/RiskLimitsProfile.mqh", "EEA_S07D1CrossState"), ("S07Tester.mq5", "D1CrossState")):
        body = src(rel).split(f"int {name}(")[1].split("\n  }")[0]
        assert "CopyClose(" in body and "PERIOD_D1,1,200" in body       # start at shift 1: the forming day is excluded
        assert "i>=150" in body                                          # SMA50 = the newest 50 of the 200 closes


def mql_state(closes):
    """Python mirror of the MQL function: closes oldest -> newest, the last 200 CLOSED days."""
    c = closes[-200:]
    if len(c) < 200:
        return 0
    s50, s200 = np.mean(c[150:]), np.mean(c)
    return 1 if s50 > s200 else (-1 if s50 < s200 else 0)


def test_mirror_matches_research_rolling_means():
    rng = np.random.default_rng(134)
    closes = 2000 + np.cumsum(rng.normal(0, 10, 400))
    import pandas as pd
    s = pd.Series(closes)
    research = np.sign(s.rolling(50).mean() - s.rolling(200).mean())
    for k in range(200, 400):                       # state for day k = closes up to day k - 1
        assert mql_state(closes[:k]) == int(research.iat[k - 1])
