"""Telegram HTML layout of the AI reports (19/10/2026)."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_bridge as ab  # noqa: E402
import report_layout as rl  # noqa: E402
from telegram_gateway_tests import GatewayCase  # noqa: E402

TAGS = re.compile(r"</?(b|i|blockquote)( expandable)?>")


def balanced(text):
    """Only our tags, each opened and closed in order."""
    stack = []
    for m in re.finditer(r"<(/?)([a-z]+)[^>]*>", text):
        if not TAGS.fullmatch(m.group(0)):
            return False
        if m.group(1):
            if not stack or stack.pop() != m.group(2):
                return False
        else:
            stack.append(m.group(2))
    return not stack


class LayoutTests(unittest.TestCase):
    def test_report_text_is_escaped_and_tags_balance(self):
        rep = {"summary": "<b>spread</b> & A<B", "confidence_label": "HIGH", "created_at_utc": 1_800_000_000,
               "findings": [{"severity": "WARN", "detail": "</blockquote><script>"}],
               "recommendations": [{"action": "RECOMMEND_REVIEW", "target": "<i>x", "proposal": "1 < 2"}]}
        text = rl.format_report("EA_DIAGNOSTICS", "Chẩn đoán EA", rep)
        self.assertTrue(text.startswith("🩺 <b>Chẩn đoán EA</b> · AI\n<i>"))
        self.assertIn("độ tin cậy cao", text)
        self.assertIn("&lt;b&gt;spread&lt;/b&gt; &amp; A&lt;B", text)
        self.assertIn("&lt;/blockquote&gt;&lt;script&gt;", text)
        self.assertTrue(balanced(text))

    def test_long_reports_shrink_to_the_limit_and_keep_the_scalp_view(self):
        long = "x" * 500
        rep = {"summary": long * 4,
               "findings": [{"severity": s, "detail": long} for s in ("WARN",) * 8 + ("INFO",) * 8],
               "recommendations": [{"action": "SCALP_VIEW", "target": f"S{i}", "proposal": "CHỜ: " + long}
                                   for i in range(8)] +
                                  [{"action": "RECOMMEND_REVIEW", "target": "t", "proposal": long}] * 6}
        text = rl.format_report("NEWS_FLASH", "Sau tin", rep, 3500)
        self.assertLessEqual(len(text), 3500)
        self.assertTrue(balanced(text))
        self.assertIn("🎯 <b>Nhận định scalp</b>", text)
        self.assertEqual(text.count("🟡"), 8)

    def test_plain_fallback_drops_tags_and_unescapes(self):
        text = rl.format_report("NEWS_FLASH", "Sau tin", {"summary": "A < B & C"})
        plain = rl.plain_text(text)
        self.assertNotIn("<b>", plain)
        self.assertIn("A < B & C", plain)


class GatewayHtmlTests(GatewayCase):
    def test_reports_go_out_as_html_and_fall_back_to_text(self):
        self.gw.run_once(poll_timeout=0)
        self.write("ai/reports/EA_DIAGNOSTICS.json", {"status": "OK", "request_id": "eea-2-9", "summary": "ổn"})
        rejected = []
        call = self.api.call

        def picky(method, params, timeout=35):
            if method == "sendMessage" and params.get("parse_mode") == "HTML" and not rejected:
                rejected.append(params["chat_id"])
                raise ConnectionError("Bad Request: can't parse entities: unexpected end tag")
            return call(method, params, timeout)

        self.api.call = picky
        self.gw.run_once(poll_timeout=0)
        self.gw.run_once(poll_timeout=0)
        diag = [m for m in self.api.sent if "Chẩn đoán EA" in m["text"]]
        self.assertEqual(len(diag), 2)                                    # both users got it
        plain = [m for m in diag if "parse_mode" not in m]
        self.assertEqual(len(plain), 1)                                   # the rejected one came back without tags
        self.assertNotIn("<b>", plain[0]["text"])
        self.assertEqual([m.get("parse_mode") for m in diag if m not in plain], ["HTML"])

    def test_plain_messages_keep_plain_text(self):
        self.feed({"update_id": 1, "message": {"message_id": 1, "text": "/help", "from": {"id": 111, "is_bot": False},
                                               "chat": {"id": 111, "type": "private"}}})
        self.assertNotIn("parse_mode", self.api.sent[-1])


class BridgeDetailTests(unittest.TestCase):
    def test_findings_and_proposals_are_kept_whole_for_telegram(self):
        req = ab.validate_request(json.dumps({
            "schema_version": "1.0", "request_id": "eea-2-1792200000-1", "request_type": "EA_DIAGNOSTICS",
            "created_at_utc": ab.utc_now(), "deadline_utc": ab.utc_now() + 60, "provider": "claude",
            "allowed_actions": ["REPORT", "WARN", "RECOMMEND_REVIEW"], "context": {}}).encode("utf-8"))
        detail = "Checkpoint runtime DEGRADED " + "y" * 250
        out = ab.validate_answer({"summary": "s", "findings": [{"severity": "WARN", "detail": detail}],
                                  "recommendations": [{"action": "RECOMMEND_REVIEW", "target": "t", "proposal": detail}]},
                                 req)
        self.assertEqual(out["findings"][0]["detail"], detail)
        self.assertEqual(out["recommendations"][0]["proposal"], detail)
        self.assertTrue(all(len(line) <= ab.MAX_LINE for line in out["display_lines"]))   # MT5 panel lines


if __name__ == "__main__":
    unittest.main()
