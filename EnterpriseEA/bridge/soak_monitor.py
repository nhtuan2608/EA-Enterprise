"""G17 soak monitor (NFR-02 no handle/memory leak, NFR-06 CPU/memory budget, NFR-07 log growth).

Samples the MT5 terminal process and the EA's own runtime counters every few minutes into
<data root>/logs/soak.jsonl and reports trends. Read-only: it never touches the EA or MT5.

  python soak_monitor.py --queue-root <MQL5/Files/EnterpriseEA> --loop      # sample every 300 s
  python soak_monitor.py --queue-root <...> --report [--hours 72]           # trend report

Process metrics: Windows via PowerShell Get-Process; Linux/Wine via /proc.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

INTERVAL = 300
PROCESS_NAMES = ("terminal64", "terminal64.exe")
# Report thresholds (per day, fitted over the window): a steady climb above these is flagged.
LEAK_MB_PER_DAY = 50.0
LEAK_HANDLES_PER_DAY = 200.0
CPU_BUDGET_PCT = 25.0            # average share of one core used by the terminal


def now() -> int:
    return int(time.time())


def sample_process_windows() -> dict | None:
    cmd = ("Get-Process terminal64 -ErrorAction SilentlyContinue | Sort-Object WorkingSet64 -Descending | "
           "Select-Object -First 1 Id,CPU,WorkingSet64,PrivateMemorySize64,HandleCount,"
           "@{n='Threads';e={$_.Threads.Count}} | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        p = json.loads(out.decode("utf-8", "replace") or "null")
    except ValueError:
        return None
    if not p:
        return None
    return {"pid": p["Id"], "cpu_seconds": float(p.get("CPU") or 0.0), "working_set_mb": p["WorkingSet64"] / 2 ** 20,
            "private_mb": p["PrivateMemorySize64"] / 2 ** 20, "handles": int(p["HandleCount"]), "threads": int(p["Threads"])}


def sample_process_linux(proc: Path = Path("/proc")) -> dict | None:
    best = None
    for d in proc.glob("[0-9]*"):
        try:
            cmdline = (d / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").lower()
        except OSError:
            continue
        if "terminal64" not in cmdline:
            continue
        try:
            stat = (d / "stat").read_text().rsplit(")", 1)[1].split()
            status = dict(line.split(":", 1) for line in (d / "status").read_text().splitlines() if ":" in line)
            fds = len(list((d / "fd").iterdir()))
        except (OSError, IndexError, ValueError):
            continue
        ticks = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        rss = int(status.get("VmRSS", "0 kB").split()[0]) / 1024
        cand = {"pid": int(d.name), "cpu_seconds": (int(stat[11]) + int(stat[12])) / ticks, "working_set_mb": rss,
                "private_mb": int(status.get("RssAnon", "0 kB").split()[0]) / 1024, "handles": fds,
                "threads": int(status.get("Threads", "0").strip())}
        if best is None or cand["working_set_mb"] > best["working_set_mb"]:
            best = cand
    return best


def sample_process() -> dict | None:
    return sample_process_windows() if os.name == "nt" else sample_process_linux()


def dir_mb(path: Path) -> float:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total / 2 ** 20


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def take_sample(root: Path, process: dict | None, previous: dict | None, at: int) -> dict:
    rt = read_json(root / "current" / "runtime_status.json")
    s = {"at_utc": at, "process_found": process is not None}
    if process:
        s.update({k: (round(v, 2) if isinstance(v, float) else v) for k, v in process.items()})
        if previous and previous.get("pid") == process["pid"] and at > previous["at_utc"]:
            s["cpu_pct"] = round(100.0 * (process["cpu_seconds"] - previous["cpu_seconds"]) / (at - previous["at_utc"]), 2)
    s.update({"runtime_state": rt.get("runtime_state"), "refresh_failures": rt.get("refresh_failure_count"),
              "max_refresh_ms": rt.get("max_refresh_duration_ms"), "runtime_instance": rt.get("runtime_instance_id"),
              "logs_mb": round(dir_mb(root / "logs"), 2), "files_mb": round(dir_mb(root), 2)})
    return s


def load_samples(path: Path, since: int = 0) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            s = json.loads(line)
            if s["at_utc"] >= since:
                out.append(s)
    return out


def slope_per_day(points: list[tuple[int, float]]) -> float:
    """Least-squares slope, units per day."""
    n = len(points)
    if n < 2:
        return 0.0
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    den = sum((x - mx) ** 2 for x, _ in points)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in points) / den * 86400


def report(samples: list[dict]) -> dict:
    """Trends over the newest run of one terminal process (a restart starts a new run)."""
    run = [s for s in samples if s.get("process_found")]
    if run:
        pid = run[-1]["pid"]
        run = [s for s in run if s["pid"] == pid]
    if len(run) < 2:
        return {"samples": len(run), "verdict": "NOT_ENOUGH_DATA"}
    hours = (run[-1]["at_utc"] - run[0]["at_utc"]) / 3600
    mem = slope_per_day([(s["at_utc"], s["private_mb"]) for s in run])
    handles = slope_per_day([(s["at_utc"], s["handles"]) for s in run])
    logs = slope_per_day([(s["at_utc"], s["logs_mb"]) for s in run])
    cpu = [s["cpu_pct"] for s in run if "cpu_pct" in s]
    cpu_avg = sum(cpu) / len(cpu) if cpu else 0.0
    flags = []
    if hours >= 12 and mem > LEAK_MB_PER_DAY:
        flags.append("MEMORY_CLIMBING")
    if hours >= 12 and handles > LEAK_HANDLES_PER_DAY:
        flags.append("HANDLES_CLIMBING")
    if cpu_avg > CPU_BUDGET_PCT:
        flags.append("CPU_ABOVE_BUDGET")
    failures = [s.get("refresh_failures") or 0 for s in run]
    if failures[-1] > failures[0]:
        flags.append("REFRESH_FAILURES")
    return {"samples": len(run), "hours": round(hours, 1), "pid": run[-1]["pid"],
            "private_mb_first": run[0]["private_mb"], "private_mb_last": run[-1]["private_mb"],
            "private_mb_per_day": round(mem, 1), "handles_first": run[0]["handles"], "handles_last": run[-1]["handles"],
            "handles_per_day": round(handles, 1), "cpu_avg_pct": round(cpu_avg, 2), "cpu_max_pct": max(cpu) if cpu else 0.0,
            "max_refresh_ms": max((s.get("max_refresh_ms") or 0) for s in run), "logs_mb_last": run[-1]["logs_mb"],
            "logs_mb_per_day": round(logs, 2), "flags": flags,
            "verdict": "OK" if not flags else "CHECK" if hours >= 12 else "PRELIMINARY"}


def report_text(r: dict) -> str:
    if r.get("verdict") == "NOT_ENOUGH_DATA":
        return f"Soak: chưa đủ mẫu ({r['samples']})."
    return (f"Soak {r['hours']}h ({r['samples']} mẫu, MT5 pid {r['pid']}): {r['verdict']} {' '.join(r['flags'])}\n"
            f"RAM riêng {r['private_mb_first']:.0f} -> {r['private_mb_last']:.0f} MB ({r['private_mb_per_day']:+.1f} MB/ngày)\n"
            f"Handle {r['handles_first']} -> {r['handles_last']} ({r['handles_per_day']:+.0f}/ngày)\n"
            f"CPU TB {r['cpu_avg_pct']:.1f}% (max {r['cpu_max_pct']:.1f}%), refresh EA max {r['max_refresh_ms']} ms\n"
            f"Log {r['logs_mb_last']:.1f} MB ({r['logs_mb_per_day']:+.2f} MB/ngày)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--interval", type=int, default=INTERVAL)
    parser.add_argument("--hours", type=float, default=0, help="report window (0 = everything)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--loop", action="store_true")
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.queue_root)
    path = root / "logs" / "soak.jsonl"
    if args.report:
        since = now() - int(args.hours * 3600) if args.hours else 0
        print(report_text(report(load_samples(path, since))))
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    while True:
        process = sample_process()
        s = take_sample(root, process, previous, now())
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(s) + "\n")
        previous = s if process else None
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
