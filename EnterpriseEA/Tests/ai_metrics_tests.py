"""G14 part 1: AI operational metrics and upgrade gates (bridge/ai_metrics.py), /ai and the weekly section."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "research" / "g10"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_metrics as am  # noqa: E402

T0 = 1_800_000_000


def iso(t):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def bridge_events():
    return [
        {"at_utc": T0 + 10, "event": "AI_REQUEST_ANSWERED", "request_id": "eea-0-1", "request_type": "NEWS_DATA_REVIEW",
         "provider": "claude", "seconds": 40},
        {"at_utc": T0 + 20, "event": "AI_REQUEST_ANSWERED", "request_id": "tg-000001-aa", "request_type": "ASK_AI",
         "provider": "claude", "seconds": 80},
        {"at_utc": T0 + 30, "event": "AI_REQUEST_FAILED", "request_id": "eea-2-2", "code": "AI_RESPONSE_NOT_JSON"},
        {"at_utc": T0 + 40, "event": "AI_REQUEST_FAILED", "request_id": "eea-0-3", "code": "AI_REQUEST_EXPIRED"},
        {"at_utc": T0 + 50, "event": "AI_CIRCUIT_OPEN"},
        {"at_utc": T0 - 9_999_999, "event": "AI_REQUEST_ANSWERED", "request_id": "old", "seconds": 999},   # outside window
    ]


def audit_events():
    return [
        {"event_type": "AI_RESPONSE_REJECTED", "occurred_at_utc": iso(T0 + 5), "entity_id": "eea-0-3",
         "reason_codes": ["AI_BRIDGE_OFFLINE"]},                                   # same request as the expiry
        {"event_type": "AI_RESPONSE_ACCEPTED", "occurred_at_utc": iso(T0 + 11), "entity_id": "eea-0-1"},
        {"event_type": "AI_RESPONSE_REJECTED", "occurred_at_utc": iso(T0 + 31), "entity_id": "eea-2-2",
         "reason_codes": ["AI_RESPONSE_NOT_JSON"]},
        {"event_type": "RUNTIME_REFRESHED", "occurred_at_utc": iso(T0 + 1)},
    ]


class MetricsTests(unittest.TestCase):
    def setUp(self):
        recs = [{"created_at_utc": T0 + 10, "recommendations": [{"action": "RECOMMEND_WINDOW_CHANGE"}]}]
        self.m = am.metrics(bridge_events(), audit_events(), recs, T0, T0 + 86400)

    def test_requests_counted_once(self):
        av = self.m["availability"]
        self.assertEqual((av["requests"], av["answered"], av["bridge_offline"], av["circuit_open"]), (4, 2, 1, 1))
        self.assertAlmostEqual(av["success_rate"], 0.5)

    def test_latency_validity_and_sources(self):
        self.assertAlmostEqual(self.m["latency_s"]["p50"], 60.0)
        self.assertEqual(self.m["latency_s"]["max"], 80.0)
        v = self.m["validity"]
        self.assertEqual((v["provider_answers"], v["schema_invalid"], v["expired"]), (3, 1, 1))
        self.assertAlmostEqual(v["valid_rate"], 2 / 3)
        self.assertEqual((v["ea_accepted"], v["ea_rejected"]), (1, 1))
        self.assertEqual(self.m["by_source"], {"EA": 3, "TELEGRAM": 1})
        self.assertEqual(self.m["safety"]["recommendation_actions"], {"RECOMMEND_WINDOW_CHANGE": 1})

    def test_gates(self):
        g = am.gates(self.m, {"REPORT", "WARN"}, True)
        self.assertTrue(g["AIG-02 schema/TTL"].startswith("CHƯA ĐỦ MẪU (3/20)"))
        self.assertTrue(g["AIG-06 không tăng rủi ro"].startswith("ĐẠT"))
        self.assertIn("CHƯA ĐẠT", am.gates(self.m, {"REPORT", "INCREASE_RISK"}, True)["AIG-06 không tăng rủi ro"])
        self.assertIn("CHƯA BẮT ĐẦU", g["AIG-03 mẫu shadow"])
        big = dict(self.m, validity=dict(self.m["validity"], provider_answers=40, valid_rate=0.97))
        self.assertTrue(am.gates(big, {"REPORT"}, True)["AIG-02 schema/TTL"].startswith("ĐẠT"))
        low = dict(big, validity=dict(big["validity"], valid_rate=0.80))
        self.assertTrue(am.gates(low, {"REPORT"}, True)["AIG-02 schema/TTL"].startswith("CHƯA ĐẠT"))

    def test_real_whitelist_has_no_risk_increase(self):
        import ai_bridge
        self.assertFalse(set(ai_bridge.ACTION_WHITELIST) & am.RISK_INCREASE_ACTIONS)

    def test_percentile_and_empty(self):
        self.assertEqual(am.percentile([], 0.5), 0.0)
        empty = am.metrics([], [], [], T0, T0 + 1)
        self.assertEqual(empty["availability"]["requests"], 0)
        self.assertIn("0 request", am.report_text(empty, am.gates(empty, {"REPORT"}, True)))


class RunTests(unittest.TestCase):
    def test_run_reads_logs_and_gateway_ai_command(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "logs").mkdir()
            (root / "logs" / "ai_bridge.jsonl").write_text("\n".join(json.dumps(e) for e in bridge_events()) + "\nnot json\n",
                                                           encoding="utf-8")
            (root / "logs" / "audit.jsonl").write_text("\n".join(json.dumps(e) for e in audit_events()), encoding="utf-8")
            text = am.run(root, 7, now=T0 + 3600)
            self.assertIn("4 request, trả lời 2 (50%)", text)
            self.assertIn("AIG-07", text)
            import telegram_gateway as tg
            from telegram_gateway_tests import FakeApi, msg
            cfg = tg.load_config(None)
            cfg["notify"]["edge"] = False      # G37: no real edge_monitor.py run here
            cfg.update(operators=[1])
            api = FakeApi()
            gw = tg.Gateway(root, cfg, api, "", clock=lambda: T0 + 3600)
            api.updates = [msg(1, 1, "/ai")]
            gw.run_once(poll_timeout=0)
            self.assertIn("4 request", api.sent[-1]["text"])
            self.assertIn("/ai", tg.HELP_VIEWER)

    def test_weekly_review_has_ai_section(self):
        import weekly_review as wr
        self.assertIn("## AI (REQ-012)", wr.ai_section(T0))


if __name__ == "__main__":
    unittest.main()
