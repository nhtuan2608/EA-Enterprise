"""Post-release flash (17/10/2026): the AI's scalp view reaches Telegram first; SCALP_VIEW stays inside NEWS_FLASH."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_bridge as ab  # noqa: E402
from telegram_gateway_tests import GatewayCase  # noqa: E402


class FlashForwardingTests(GatewayCase):
    def test_flash_puts_the_scalp_view_first(self):
        self.gw.run_once(poll_timeout=0)
        self.write("ai/reports/NEWS_FLASH.json", {
            "status": "OK", "request_id": "eea-5-1", "summary": "CPI cao hơn dự báo, USD tăng mạnh",
            "findings": [{"severity": "WARN", "detail": "spread còn giãn"}],
            "recommendations": [{"action": "SCALP_VIEW", "target": "XAUUSD", "proposal": "NÊN SCALP BÁN: -1.4 ATR"},
                                {"action": "SCALP_VIEW", "target": "EURUSD", "proposal": "CHỜ: spread còn giãn"}]})
        self.gw.run_once(poll_timeout=0)
        flash = [t for t in self.texts() if t.startswith("Sau tin (AI)")]
        self.assertEqual(len(flash), 2)                                   # operator and viewer
        lines = flash[0].splitlines()
        self.assertEqual(lines[1], "Nhận định scalp (AI, EA không tự vào lệnh):")
        self.assertEqual(lines[2:4], ["XAUUSD: NÊN SCALP BÁN: -1.4 ATR", "EURUSD: CHỜ: spread còn giãn"])
        self.assertIn("[WARN] spread còn giãn", flash[0])

    def test_four_hour_review_is_forwarded_and_both_can_be_muted(self):
        self.gw.run_once(poll_timeout=0)
        self.write("ai/reports/NEWS_EVENT_REVIEW.json", {"status": "OK", "request_id": "eea-1-1", "summary": "đủ 240 phút"})
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(t.startswith("Đánh giá sau tin (đủ 4 giờ) (AI)") for t in self.texts()), 2)
        self.config["notify"].update(post_news=False, post_news_review=False)
        sent = len(self.texts())
        self.write("ai/reports/NEWS_EVENT_REVIEW.json", {"status": "OK", "request_id": "eea-1-2", "summary": "x"})
        self.write("ai/reports/NEWS_FLASH.json", {"status": "OK", "request_id": "eea-5-2", "summary": "y"})
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(len(self.texts()), sent)


class BridgeFlashTests(unittest.TestCase):
    def request(self, request_type, actions):
        return json.dumps({"schema_version": "1.0", "request_id": "eea-5-1792200000-1", "request_type": request_type,
                           "created_at_utc": ab.utc_now(), "deadline_utc": ab.utc_now() + 60, "provider": "claude",
                           "allowed_actions": actions, "context": {"minutes_since_release": 3}}).encode("utf-8")

    def test_scalp_view_only_inside_news_flash(self):
        req = ab.validate_request(self.request("NEWS_FLASH", ["REPORT", "WARN", "SCALP_VIEW"]))
        ok = ab.validate_answer({"summary": "x", "recommendations": [
            {"action": "SCALP_VIEW", "target": "XAUUSD", "proposal": "KHÔNG NÊN: phản ứng nhỏ"}]}, req)
        self.assertEqual(ok["recommendations"][0]["action"], "SCALP_VIEW")
        for request_type in ("NEWS_PRE_BRIEF", "ASK_AI", "NEWS_EVENT_REVIEW"):
            with self.subTest(request_type=request_type), self.assertRaises(ab.BridgeError):
                ab.validate_request(self.request(request_type, ["REPORT", "SCALP_VIEW"]))

    def test_only_the_flash_prompt_allows_an_opinion(self):
        flash = ab.build_prompt(ab.validate_request(self.request("NEWS_FLASH", ["REPORT", "SCALP_VIEW"])))
        self.assertIn("EA không bao giờ tự vào lệnh", flash)
        self.assertIn("NÊN SCALP MUA, NÊN SCALP BÁN, CHỜ hoặc KHÔNG NÊN", flash)
        brief = ab.build_prompt(ab.validate_request(self.request("NEWS_PRE_BRIEF", ["REPORT"])))
        self.assertIn("Bạn KHÔNG được đặt lệnh, đề xuất giá, lot, entry/exit", brief)
        self.assertNotIn("SCALP_VIEW", brief)


if __name__ == "__main__":
    unittest.main()
