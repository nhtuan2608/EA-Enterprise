"""EA watchdog (19/10/2026): Telegram says so when the EA stops writing live_status.json, and when it is back."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import telegram_gateway as tg  # noqa: E402
from telegram_gateway_tests import GatewayCase  # noqa: E402


class EaStaleTests(GatewayCase):
    def live(self, age):
        self.write("current/live_status.json", {"document_version": "live-status-v1.0.0",
                                                 "written_at_utc": self.clock.t - age})

    def alerts(self):
        return [t for t in self.texts() if "EA không ghi trạng thái" in t]

    def test_alert_once_remind_hourly_and_recover(self):
        self.live(60)
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.alerts(), [])                                # fresh: nothing
        self.live(tg.EA_STALE_ALERT)
        self.gw.run_once(poll_timeout=0)
        alerts = self.alerts()
        self.assertEqual(len(alerts), 2)                                   # operator and viewer
        self.assertTrue(alerts[0].startswith("CẢNH BÁO: EA không ghi trạng thái"))
        self.clock.t += 10 * 60
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(len(self.alerts()), 2)                            # no repeat inside the hour
        self.gw = self.new_gateway()                                       # a gateway restart keeps the state
        self.clock.t += tg.EA_STALE_REMIND
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(len(self.alerts()), 4)
        self.assertTrue(self.alerts()[-1].startswith("Nhắc lại:"))
        self.live(30)
        self.gw.run_once(poll_timeout=0)
        self.assertTrue(any(t.startswith("EA đã chạy lại") for t in self.texts()))
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(sum(t.startswith("EA đã chạy lại") for t in self.texts()), 2)   # once per user

    def test_no_status_file_and_muted_flag_send_nothing(self):
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.alerts(), [])
        self.config["notify"]["ea_stale"] = False
        self.live(3600)
        self.gw.run_once(poll_timeout=0)
        self.assertEqual(self.alerts(), [])


if __name__ == "__main__":
    unittest.main()
