"""G20 weekly review (roadmap G5): real trades next to the virtual result of every candidate.

  python weekly_review.py                       # the last 7 days
  python weekly_review.py --since 2026-10-05 --until 2026-10-12

Per setup and profile:
  REAL        closed EA trades from logs/trades.jsonl (realized money / initial risk = R)
  MODEL(EXEC) the G10 "tm" model on the same executed candidates: REAL - MODEL is the
              execution gap (slippage, spread at entry, manager timing)
  BLOCKED     virtual result of candidates that did not trade, per reason (value of each filter)
  ALONE       every candidate, as if the setup had run on its own (compare with the research)
Writes results/weekly_review_<until>.md and prints it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import candidates_eval as ce
import context

# Out-of-sample expectancy from the G10 study (R per trade, costs included) for comparison.
RESEARCH = {"S02_SCALP": -0.36, "S02_SWING": -0.14, "S04_SCALP": -0.22, "S04_SWING": 0.0, "S06_SWING": 0.10,
            "S06B_SWING": 0.29,  # G23 test 2021-2025
            "T2_POSITION": 0.17}  # G38 test 2021-2025 (gap fills)


def trades_path() -> Path:
    return context.DATA.parent / "logs" / "trades.jsonl"


def load_trades(path: Path, since: int, until: int) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            if since <= int(t.get("exit_utc") or 0) < until:
                out.append(t)
    return out


def real_summary(trades: list[dict]) -> dict:
    known = [t for t in trades if t.get("realized_known") and t.get("realized_r") is not None]
    n = len(known)
    total_r = sum(float(t["realized_r"]) for t in known)
    return {"n": n, "unknown": len(trades) - n, "exp": total_r / n if n else 0.0, "total_r": total_r,
            "win": sum(1 for t in known if float(t["realized_r"]) > 0) / n if n else 0.0,
            "money": sum(float(t.get("realized_money", 0)) for t in trades if t.get("realized_known"))}


def build(trades: list[dict], evaluated: list[dict]) -> dict:
    keys = sorted({f"{t.get('setup', '?')}_{t.get('profile', '?')}" for t in trades} |
                  {f"{e['setup']}_{e['profile']}" for e in evaluated})
    rep = ce.report(evaluated)
    out = {}
    for key in keys:
        groups = rep.get(key, {})
        out[key] = {
            "real": real_summary([t for t in trades if f"{t.get('setup')}_{t.get('profile')}" == key]),
            "model_exec": groups.get("EXECUTED", {"n": 0, "exp": 0.0, "win": 0.0}),
            "blocked": {g: s for g, s in groups.items() if g not in ("ALL", "EXECUTED", "NO_BARS_YET")},
            "alone": groups.get("ALL", {"n": 0, "exp": 0.0, "win": 0.0}),
            "no_bars_yet": groups.get("NO_BARS_YET", {"n": 0})["n"],
            "research": RESEARCH.get(key),
        }
    return out


def fmt(s: dict) -> str:
    return f"n={s['n']} exp={s['exp']:+.2f}R win={s['win']:.0%}" if s.get("n") else "n=0"


def markdown(review: dict, since: int, until: int) -> str:
    day = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")  # noqa: E731
    lines = [f"# Đánh giá tuần {day(since)} → {day(until)}", "",
             "| Setup | Lệnh thật | Mô hình trên lệnh đã vào | Như chạy một mình | Nghiên cứu G10 |",
             "|---|---|---|---|---|"]
    for key, r in review.items():
        real = r["real"]
        real_txt = fmt(real) + (f" tiền {real['money']:+.2f}" if real["n"] else "") + \
            (f" (+{real['unknown']} chưa rõ)" if real["unknown"] else "")
        research = "--" if r["research"] is None else f"{r['research']:+.2f}R"
        lines.append(f"| {key} | {real_txt} | {fmt(r['model_exec'])} | {fmt(r['alone'])} | {research} |")
    lines += ["", "## Candidate không vào lệnh (kết quả ảo theo lý do)", ""]
    for key, r in review.items():
        if r["blocked"] or r["no_bars_yet"]:
            parts = [f"{g}: {fmt(s)}" for g, s in r["blocked"].items()]
            if r["no_bars_yet"]:
                parts.append(f"chưa đủ nến: {r['no_bars_yet']}")
            lines.append(f"- **{key}**: " + "; ".join(parts))
    lines += ["", "Ghi chú: kết quả ảo dùng mô hình Trade Manager của G10 (có chi phí, không trượt giá; "
              "trong một nến chạm SL được tính trước TP). Lệnh thật: tiền thực / rủi ro ban đầu tại SL."]
    return "\n".join(lines) + "\n"


def ai_section(until: int) -> str:
    """REQ-012 operational AI metrics for the same week (bridge/ai_metrics.py)."""
    bridge_dir = Path(__file__).resolve().parents[2] / "bridge"
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    try:
        import ai_metrics
        return "\n## AI (REQ-012)\n\n```\n" + ai_metrics.run(context.DATA.parent, 7, now=until) + "\n```\n"
    except Exception as exc:  # the trading review stands on its own
        return f"\n## AI (REQ-012)\n\nKhông tính được: {type(exc).__name__}\n"


def parity_section() -> str:
    """G48: does the EA emit the signals the research finds on the same bars (forward and its own replay)?"""
    head = "\n## Khớp tín hiệu EA ↔ nghiên cứu (G48)\n\n"
    try:
        import signal_parity as sp
        res = sp.run()
        res["replay"] = sp.replay_parity()
        return head + sp.text(res).replace("\n", "  \n") + "\n"
    except Exception as exc:      # the weekly review must not fail on the parity check
        return head + f"không chạy được: {exc}\n"


def main(argv: list[str]) -> None:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    until = today + timedelta(days=1)
    since = until - timedelta(days=7)
    if "--since" in argv:
        since = datetime.fromisoformat(argv[argv.index("--since") + 1]).replace(tzinfo=timezone.utc)
    if "--until" in argv:
        until = datetime.fromisoformat(argv[argv.index("--until") + 1]).replace(tzinfo=timezone.utc)
    s, u = int(since.timestamp()), int(until.timestamp())
    trades = load_trades(trades_path(), s, u)
    rows = [r for r in ce.load(ce.ledger_path(), s) if int(r.get("closed_utc", 0)) < u]
    evaluated = ce.evaluate_rows(rows)
    text = markdown(build(trades, evaluated), s, u) + ai_section(u)
    text += parity_section()
    ce.OUT.mkdir(exist_ok=True)
    (ce.OUT / f"weekly_review_{until.strftime('%Y-%m-%d')}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
