"""G21 supervisor (bridge/supervisor.py): restart, backoff, crash-loop pause, alerts, heartbeat."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

import supervisor as sv  # noqa: E402


class FakeProc:
    count = 0

    def __init__(self):
        FakeProc.count += 1
        self.pid = 1000 + FakeProc.count
        self.code = None
        self.terminated = False

    def poll(self):
        return self.code

    def terminate(self):
        self.terminated = True
        self.code = 1


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


class SupervisorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = Clock()
        self.spawned, self.alerts = [], []
        specs = [{"name": "ai_bridge", "script": "ai_bridge.py", "args": []},
                 {"name": "telegram", "script": "telegram_gateway.py", "args": []}]
        self.sup = sv.Supervisor(self.root, specs, self.spawn, self.alerts.append, clock=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def spawn(self, spec):
        p = FakeProc()
        self.spawned.append((spec["name"], p))
        return p

    def proc(self, name):
        return self.sup.state[name]["proc"]

    def heartbeat(self):
        return json.loads((self.root / "supervisor_heartbeat.json").read_text(encoding="utf-8"))

    def test_starts_every_service_and_writes_heartbeat(self):
        self.sup.tick()
        self.assertEqual([n for n, _ in self.spawned], ["ai_bridge", "telegram"])
        hb = self.heartbeat()
        self.assertTrue(hb["services"]["telegram"]["running"])
        self.assertEqual(hb["version"], sv.VERSION)

    def test_restart_with_backoff_and_alert(self):
        self.sup.tick()
        self.proc("telegram").code = 1
        self.sup.tick()
        self.assertIsNone(self.proc("telegram"))
        self.assertEqual(len(self.alerts), 1)
        self.assertIn("telegram đã dừng (mã 1), chạy lại sau 5s", self.alerts[0])
        self.clock.t += 4
        self.sup.tick()
        self.assertIsNone(self.proc("telegram"))
        self.clock.t += 2
        self.sup.tick()
        self.assertIsNotNone(self.proc("telegram"))
        self.assertEqual(self.sup.state["telegram"]["restarts"], 1)
        # Second exit right away: longer wait; the alert is throttled.
        self.proc("telegram").code = 2
        self.sup.tick()
        self.assertEqual(self.sup.state["telegram"]["next_start"] - self.clock.t, sv.BACKOFF[1])
        self.assertEqual(len(self.alerts), 1)

    def test_stable_service_resets_backoff(self):
        self.sup.tick()
        self.proc("ai_bridge").code = 1
        self.sup.tick()
        self.clock.t += 6
        self.sup.tick()
        self.assertEqual(self.sup.state["ai_bridge"]["streak"], 1)
        self.clock.t += sv.STABLE_SECONDS
        self.sup.tick()
        self.assertEqual(self.sup.state["ai_bridge"]["streak"], 0)

    def test_crash_loop_pauses_service(self):
        self.sup.tick()
        # Backoff waits included (5+15+60+300 s), the 5th exit still falls inside the 10-minute window.
        for _ in range(sv.CRASH_LIMIT):
            p = self.proc("ai_bridge")
            if p is None:
                self.clock.t = self.sup.state["ai_bridge"]["next_start"]
                self.sup.tick()
                p = self.proc("ai_bridge")
            p.code = 1
            self.clock.t += 1
            self.sup.tick()
        st = self.sup.state["ai_bridge"]
        self.assertGreater(st["paused_until"], self.clock.t)
        self.clock.t += 400
        self.sup.tick()
        self.assertIsNone(self.proc("ai_bridge"))                       # still paused
        self.assertTrue(self.heartbeat()["services"]["ai_bridge"]["paused"])
        self.clock.t = st["paused_until"] + 1
        self.sup.tick()
        self.assertIsNotNone(self.proc("ai_bridge"))
        log = (self.root / "logs" / "supervisor.jsonl").read_text(encoding="utf-8")
        self.assertIn("CRASH_LOOP_PAUSED", log)

    def test_spawn_failure_is_logged_and_retried_later(self):
        def broken(spec):
            raise OSError("no python")
        self.sup.spawn = broken
        self.sup.tick()
        self.assertIsNone(self.proc("ai_bridge"))
        self.assertIn("không chạy được", self.alerts[0])
        self.assertGreater(self.sup.state["ai_bridge"]["next_start"], self.clock.t)

    def test_alert_failure_never_stops_supervision(self):
        def failing(text):
            raise ConnectionError("telegram down")
        self.sup.notify = failing
        self.sup.tick()
        self.proc("telegram").code = 1
        self.sup.tick()
        self.assertIn("ALERT_FAILED", (self.root / "logs" / "supervisor.jsonl").read_text(encoding="utf-8"))

    def test_stop_all_terminates_children(self):
        self.sup.tick()
        procs = [p for _, p in self.spawned]
        self.sup.stop_all()
        self.assertTrue(all(p.terminated for p in procs))


class ServiceListTests(unittest.TestCase):
    def test_three_services_with_queue_root(self):
        specs = sv.services(Path("Q"), "cfg.json")
        self.assertEqual([s["name"] for s in specs], ["ai_bridge", "telegram", "soak"])
        for s in specs:
            self.assertIn("--loop", s["args"])
            self.assertIn("Q", s["args"])
        self.assertIn("cfg.json", specs[1]["args"])

    def test_gateway_status_shows_supervisor(self):
        import telegram_gateway as tg
        d = {"supervisor_age_s": 10, "supervisor_services": {"ai_bridge": "RUNNING", "telegram": "RUNNING (chạy lại 2)"}}
        self.assertEqual(tg.Gateway.supervisor_text(d), "ai_bridge RUNNING, telegram RUNNING (chạy lại 2)")
        self.assertIn("OFFLINE", tg.Gateway.supervisor_text({"supervisor_age_s": 500}))
        self.assertIn("chạy tay", tg.Gateway.supervisor_text({"supervisor_age_s": None}))


if __name__ == "__main__":
    unittest.main()
