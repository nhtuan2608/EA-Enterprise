"""EnterpriseEA process supervisor for Windows (G21): keeps the AI bridge, the Telegram gateway and
the soak monitor running. Start it once (bridge/start_all.ps1); it restarts any service that
exits, backs off on repeated crashes, and alerts the Telegram operators directly (so an alert
still goes out when the gateway itself is the service that died). No scheduled task is created.
On Linux use the systemd units instead (Restart=always).

  python supervisor.py --queue-root <MQL5/Files/EnterpriseEA> --config telegram.json

The bot token comes from EEA_TELEGRAM_TOKEN (or token_file in the config); it is never logged.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "supervisor-v1.0.0"
CHECK_SECONDS = 15
BACKOFF = (5, 15, 60, 300)          # wait before the n-th consecutive restart
CRASH_WINDOW = 600                  # CRASH_LIMIT exits in this window: pause the service
CRASH_LIMIT = 5                     # with BACKOFF the 5th exit lands ~380 s after the 1st, inside the window
CRASH_PAUSE = 600
STABLE_SECONDS = 300                # a service up this long resets its backoff
ALERT_THROTTLE = 900
MAX_OUT_LOG = 5 * 2 ** 20


def now() -> float:
    return time.time()


def services(root: Path, config_path: str) -> list[dict]:
    py = sys.executable
    q = str(root)
    return [
        {"name": "ai_bridge", "script": "ai_bridge.py", "args": [py, str(HERE / "ai_bridge.py"), "--queue-root", q, "--loop"]},
        {"name": "telegram", "script": "telegram_gateway.py",
         "args": [py, str(HERE / "telegram_gateway.py"), "--queue-root", q, "--config", config_path, "--loop"]},
        {"name": "soak", "script": "soak_monitor.py", "args": [py, str(HERE / "soak_monitor.py"), "--queue-root", q, "--loop"]},
    ]


def redact(text: str, token: str) -> str:
    return str(text).replace(token, "<token>") if token else str(text)


class Supervisor:
    def __init__(self, root: Path, specs: list[dict], spawn, notify, clock=now, log_dir: Path | None = None):
        self.root = Path(root)
        self.specs = specs
        self.spawn = spawn            # spawn(spec) -> process with poll()/terminate()/pid
        self.notify = notify          # notify(text)
        self.clock = clock
        self.log_path = (log_dir or self.root / "logs") / "supervisor.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = {s["name"]: {"proc": None, "started": 0.0, "exits": [], "streak": 0, "next_start": 0.0,
                                  "paused_until": 0.0, "alert_at": 0.0, "restarts": 0} for s in specs}

    def log(self, event: str, **fields):
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at_utc": int(self.clock()), "event": event, **fields}, ensure_ascii=False) + "\n")

    def alert(self, name: str, text: str):
        st = self.state[name]
        if self.clock() - st["alert_at"] < ALERT_THROTTLE:
            return
        st["alert_at"] = self.clock()
        try:
            self.notify(text)
        except Exception as exc:  # an alert failure never stops supervision
            self.log("ALERT_FAILED", service=name, detail=str(exc)[:160])

    def start(self, spec: dict):
        st = self.state[spec["name"]]
        try:
            st["proc"] = self.spawn(spec)
        except OSError as exc:
            st["proc"] = None
            st["next_start"] = self.clock() + BACKOFF[-1]
            self.log("START_FAILED", service=spec["name"], detail=str(exc)[:160])
            self.alert(spec["name"], f"SUPERVISOR: không chạy được {spec['name']}: {exc}")
            return
        st["started"] = self.clock()
        self.log("STARTED", service=spec["name"], pid=getattr(st["proc"], "pid", None))

    def tick(self):
        t = self.clock()
        for spec in self.specs:
            name = spec["name"]
            st = self.state[name]
            proc = st["proc"]
            if proc is not None:
                code = proc.poll()
                if code is None:
                    if st["streak"] and t - st["started"] >= STABLE_SECONDS:
                        st["streak"] = 0
                    continue
                st["proc"] = None
                st["exits"] = [x for x in st["exits"] if x > t - CRASH_WINDOW] + [t]
                st["streak"] += 1
                self.log("EXITED", service=name, code=code, uptime_s=int(t - st["started"]), streak=st["streak"])
                if len(st["exits"]) >= CRASH_LIMIT:
                    st["paused_until"] = t + CRASH_PAUSE
                    self.log("CRASH_LOOP_PAUSED", service=name, exits=len(st["exits"]))
                    self.alert(name, f"SUPERVISOR: {name} chết {len(st['exits'])} lần trong 10 phút, tạm dừng 10 phút. "
                                     f"Xem logs/{name}.out.log")
                else:
                    wait = BACKOFF[min(st["streak"], len(BACKOFF)) - 1]
                    st["next_start"] = t + wait
                    self.alert(name, f"SUPERVISOR: {name} đã dừng (mã {code}), chạy lại sau {wait}s.")
            if st["proc"] is None and t >= max(st["next_start"], st["paused_until"]):
                if st["started"]:
                    st["restarts"] += 1
                self.start(spec)
        self.heartbeat()

    def heartbeat(self):
        status = {}
        for spec in self.specs:
            st = self.state[spec["name"]]
            running = st["proc"] is not None and st["proc"].poll() is None
            status[spec["name"]] = {"running": running, "pid": getattr(st["proc"], "pid", None) if running else None,
                                    "restarts": st["restarts"], "paused": st["paused_until"] > self.clock()}
        path = self.root / "supervisor_heartbeat.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"version": VERSION, "at_utc": int(self.clock()), "services": status}), encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.2 * (attempt + 1))

    def stop_all(self):
        for spec in self.specs:
            proc = self.state[spec["name"]]["proc"]
            if proc is not None and proc.poll() is None:
                proc.terminate()
                self.log("STOPPED", service=spec["name"])


# ---------------------------------------------------------------------------
# Real process handling and alerts
# ---------------------------------------------------------------------------
def make_spawn(root: Path, env: dict):
    def spawn(spec: dict):
        out = root / "logs" / f"{spec['name']}.out.log"
        if out.exists() and out.stat().st_size > MAX_OUT_LOG:
            os.replace(out, out.with_suffix(".log.1"))
        fh = out.open("ab")
        try:
            return subprocess.Popen(spec["args"], cwd=str(HERE.parent), env=env, stdout=fh, stderr=subprocess.STDOUT)
        finally:
            fh.close()
    return spawn


def take_over(scripts: list[str]) -> int:
    """Stop copies of the services started by hand, so each runs once (Windows)."""
    if os.name != "nt":
        return 0
    pattern = "|".join(s.replace(".", "\\.") for s in scripts)
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match '"
           + pattern + "' -and $_.CommandLine -notmatch 'supervisor\\.py' } | ForEach-Object { "
           "Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=60).stdout
    return len([l for l in out.decode("utf-8", "replace").split() if l.strip().isdigit()])


def make_notify(config_path: str, token: str):
    try:
        operators = json.loads(Path(config_path).read_text(encoding="utf-8")).get("operators", [])
    except (OSError, ValueError):
        operators = []

    def notify(text: str):
        if not token:
            return
        sys.path.insert(0, str(HERE))
        import telegram_gateway as tg
        api = tg.TelegramApi(token)
        for chat in operators:
            api.call("sendMessage", {"chat_id": int(chat), "text": text}, timeout=20)
    return notify


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--config", default=str(HERE / "telegram.json"))
    parser.add_argument("--no-takeover", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.queue_root)
    sys.path.insert(0, str(HERE))
    import telegram_gateway as tg
    token = tg.load_token(tg.load_config(args.config)) if Path(args.config).exists() else ""
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    if token:
        env["EEA_TELEGRAM_TOKEN"] = token
    specs = services(root, args.config)
    if not Path(args.config).exists():
        specs = [s for s in specs if s["name"] != "telegram"]
    sup = Supervisor(root, specs, make_spawn(root, env), make_notify(args.config, token))
    if not args.no_takeover:
        sup.log("TAKEOVER", stopped=take_over([s["script"] for s in specs]))
    sup.log("SUPERVISOR_STARTED", version=VERSION, pid=os.getpid(), services=[s["name"] for s in specs])
    try:
        sup.notify("SUPERVISOR: đã khởi động, giám sát " + ", ".join(s["name"] for s in specs))
    except Exception as exc:
        sup.log("ALERT_FAILED", detail=redact(exc, token)[:160])
    try:
        while True:
            try:
                sup.tick()
            except Exception as exc:  # supervision itself must keep going
                sup.log("SUPERVISOR_ERROR", detail=redact(exc, token)[:200])
            time.sleep(CHECK_SECONDS)
    except KeyboardInterrupt:
        sup.stop_all()
        sup.log("SUPERVISOR_STOPPED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
