"""G60: live_status.json carries the risk and News Guard settings; init message says what the EA may do;
the readiness script reads the files the live path really writes."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class LiveStatusG60Tests(unittest.TestCase):
    def setUp(self):
        self.shell = read("EnterpriseEA.mq5")

    def test_risk_json_resolves_policy_then_limits(self):
        body = section(self.shell, "string EEA_LiveStatusRiskJson()")
        a = body.index("EEA_ControlledLiveResolvePolicy(")
        b = body.index("EEA_RiskLimitsForPolicy(policy.committed_policy")
        self.assertLess(a, b)

    def test_risk_json_keys(self):
        body = section(self.shell, "string EEA_LiveStatusRiskJson()")
        for key in ("per_trade_percent", "open_percent", "daily_percent", "weekly_percent",
                    "S04_percent", "S06B_percent", "T2_percent"):
            self.assertIn('"' + key + '"', body)
        for setup in ("S04", "S06B", "T2"):
            self.assertIn('p*EEA_SetupRiskWeight("%s")' % setup, body)

    def test_write_live_status_has_risk_and_news(self):
        body = section(self.shell, "void EEA_WriteLiveStatus()")
        self.assertIn('"risk",EEA_LiveStatusRiskJson()', body)
        self.assertIn('"news"', body)
        self.assertIn("g_news.cfg.allow_when_unknown", body)
        self.assertIn("g_news.cfg.ignore_keywords", body)

    def test_init_messages(self):
        self.assertIn("live entries armed", self.shell)
        self.assertIn("execution enabled, live entries NOT armed", self.shell)
        self.assertIn("observer only, no execution authority", self.shell)
        prints = [l for l in self.shell.split("\n") if "Print(" in l]
        self.assertFalse(any("without execution authority" in l for l in prints))
        self.assertEqual(sum("no execution authority" in l for l in prints), 1)

    def test_readiness_script(self):
        ps = read("tools/verify_live_readiness.ps1")
        self.assertIn("live_session.json", ps)
        self.assertIn("live_status.json", ps)
        code = "\n".join(l for l in ps.split("\n") if not l.lstrip().startswith("#"))
        self.assertNotIn("live_authorization.json", code)
        line = [l for l in ps.split("\n") if l.startswith('Check "runtime_current"') or "RUNTIME_EVIDENCE_CURRENT" in l]
        self.assertTrue(line)
        self.assertFalse(any("new_entries_blocked" in l for l in line))


if __name__ == "__main__":
    unittest.main()
