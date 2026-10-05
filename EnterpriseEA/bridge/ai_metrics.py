"""G14 part 1: AI operational metrics and upgrade-gate status (master specification 13.1, 13.4; REQ-012).

Reads what already exists, read-only:
  logs/ai_bridge.jsonl          bridge: answered / failed (code) / circuit / latency (seconds)
  logs/audit.jsonl              EA: AI_REQUEST_QUEUED, AI_RESPONSE_ACCEPTED / REJECTED, AI_CIRCUIT_OPEN
  logs/ai_recommendations.jsonl EA: every OK response with its findings and recommendations

  python ai_metrics.py --queue-root <MQL5/Files/EnterpriseEA> [--days 7]

Decision and outcome metrics (13.1 Decision / Outcome) and gates AIG-03..05 need the
Level 1 shadow comparison, which does not exist yet; they are reported as not started.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCHEMA_CODES = {"AI_RESPONSE_NOT_JSON", "AI_RESPONSE_SCHEMA_INVALID", "AI_RESPONSE_SUMMARY_MISSING"}
SAFETY_CODES = {"AI_ACTION_NOT_ALLOWED"}
PROVIDER_CODES = {"AI_PROVIDER_FAILED", "AI_PROVIDER_UNAVAILABLE", "AI_PROVIDER_TIMEOUT"}
# Proposed AIG-02 threshold (master specification leaves it to approval): share of provider
# answers that pass the JSON contract, over at least this many answers.
AIG02_MIN_VALID = 0.95
AIG02_MIN_SAMPLE = 20
# Actions an AI could use to add risk; none may ever be in the whitelist (AIG-06).
RISK_INCREASE_ACTIONS = {"INCREASE_RISK", "OPEN", "BUY", "SELL", "RESUME_ENTRIES", "ENABLE"}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def audit_utc(e: dict) -> int:
    try:
        return int(time.mktime(time.strptime(e.get("occurred_at_utc", ""), "%Y-%m-%dT%H:%M:%SZ")) - time.timezone)
    except (ValueError, OverflowError):
        return 0


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def source_of(request_id: str) -> str:
    return "TELEGRAM" if str(request_id).startswith("tg-") else "EA"


def metrics(bridge: list[dict], audit: list[dict], recs: list[dict], since: int, until: int) -> dict:
    b = [e for e in bridge if since <= int(e.get("at_utc", 0)) < until]
    a = [e for e in audit if str(e.get("event_type", "")).startswith("AI_") and since <= audit_utc(e) < until]
    r = [x for x in recs if since <= int(x.get("created_at_utc", 0)) < until]
    answered = [e for e in b if e.get("event") == "AI_REQUEST_ANSWERED"]
    failed = [e for e in b if e.get("event") == "AI_REQUEST_FAILED"]
    offline = [e for e in a if e.get("event_type") == "AI_RESPONSE_REJECTED" and "AI_BRIDGE_OFFLINE" in (e.get("reason_codes") or [])]
    codes: dict[str, int] = {}
    for e in failed:
        codes[e.get("code", "?")] = codes.get(e.get("code", "?"), 0) + 1
    # One request can be marked offline by the EA and later expire in the bridge: count ids once.
    total = len({e.get("request_id") for e in answered + failed} | {e.get("entity_id") for e in offline})
    provider_calls = len(answered) + sum(n for c, n in codes.items() if c in PROVIDER_CODES | SCHEMA_CODES | SAFETY_CODES)
    schema_bad = sum(n for c, n in codes.items() if c in SCHEMA_CODES)
    safety_bad = sum(n for c, n in codes.items() if c in SAFETY_CODES)
    latency = [float(e.get("seconds", 0)) for e in answered]
    by_type: dict[str, dict] = {}
    for e in answered:
        t = by_type.setdefault(e.get("request_type", "?"), {"answered": 0, "failed": 0})
        t["answered"] += 1
    by_source = {"EA": 0, "TELEGRAM": 0}
    for e in answered + failed:
        by_source[source_of(e.get("request_id", ""))] += 1
    by_provider: dict[str, int] = {}
    for e in answered:
        by_provider[e.get("provider", "?")] = by_provider.get(e.get("provider", "?"), 0) + 1
    actions: dict[str, int] = {}
    for x in r:
        for rec in x.get("recommendations", []) or []:
            actions[rec.get("action", "?")] = actions.get(rec.get("action", "?"), 0) + 1
    ea_accepted = sum(1 for e in a if e.get("event_type") == "AI_RESPONSE_ACCEPTED")
    ea_rejected = [e for e in a if e.get("event_type") == "AI_RESPONSE_REJECTED" and e not in offline]
    return {
        "window_days": round((until - since) / 86400, 1),
        "availability": {"requests": total, "answered": len(answered), "success_rate": len(answered) / total if total else 0.0,
                         "failures": codes, "bridge_offline": len(offline),
                         "circuit_open": sum(1 for e in b if e.get("event") == "AI_CIRCUIT_OPEN") +
                                         sum(1 for e in a if e.get("event_type") == "AI_CIRCUIT_OPEN"),
                         "bridge_errors": sum(1 for e in b if e.get("event") == "AI_BRIDGE_ERROR")},
        "latency_s": {"p50": percentile(latency, 0.5), "p95": percentile(latency, 0.95), "max": max(latency, default=0.0)},
        "validity": {"provider_answers": provider_calls, "schema_invalid": schema_bad,
                     "valid_rate": (provider_calls - schema_bad - safety_bad) / provider_calls if provider_calls else 0.0,
                     "expired": codes.get("AI_REQUEST_EXPIRED", 0), "ea_accepted": ea_accepted, "ea_rejected": len(ea_rejected)},
        "safety": {"actions_outside_whitelist": safety_bad, "recommendation_actions": actions},
        "by_type": by_type, "by_source": by_source, "by_provider": by_provider,
        "reports_recorded": len(r),
    }


def gates(m: dict, whitelist: set[str], circuit_configured: bool) -> dict:
    v = m["validity"]
    if v["provider_answers"] < AIG02_MIN_SAMPLE:
        g02 = f"CHƯA ĐỦ MẪU ({v['provider_answers']}/{AIG02_MIN_SAMPLE})"
    else:
        g02 = "ĐẠT" if v["valid_rate"] >= AIG02_MIN_VALID and m["safety"]["actions_outside_whitelist"] == 0 else "CHƯA ĐẠT"
    unsafe = sorted(whitelist & RISK_INCREASE_ACTIONS)
    return {
        "AIG-01 baseline cố định": "THEO DÕI (config_version các setup đã cố định; khoá khi bắt đầu shadow)",
        "AIG-02 schema/TTL": g02 + f", hợp lệ {v['valid_rate']:.0%}, ngoài whitelist {m['safety']['actions_outside_whitelist']}",
        "AIG-03 mẫu shadow": "CHƯA BẮT ĐẦU (cần Level 1 shadow)",
        "AIG-04 hiệu quả ngoài mẫu": "CHƯA BẮT ĐẦU (cần Level 1 shadow)",
        "AIG-05 DD/tail": "CHƯA BẮT ĐẦU (cần Level 1 shadow)",
        "AIG-06 không tăng rủi ro": "ĐẠT (whitelist chỉ báo cáo/cảnh báo/khuyến nghị)" if not unsafe else f"CHƯA ĐẠT {unsafe}",
        "AIG-07 kill switch/circuit": "ĐẠT (InpAiEnabled, circuit breaker, Level 0 cần người duyệt)" if circuit_configured else "CHƯA ĐẠT",
    }


def report_text(m: dict, g: dict) -> str:
    av, lat, v = m["availability"], m["latency_s"], m["validity"]
    fails = ", ".join(f"{c} {n}" for c, n in sorted(av["failures"].items())) or "--"
    lines = [f"AI {m['window_days']} ngày: {av['requests']} request, trả lời {av['answered']} ({av['success_rate']:.0%})",
             f"Lỗi: {fails}; bridge offline {av['bridge_offline']}; circuit {av['circuit_open']}",
             f"Độ trễ p50 {lat['p50']:.0f}s p95 {lat['p95']:.0f}s max {lat['max']:.0f}s",
             f"Hợp lệ {v['valid_rate']:.0%} trên {v['provider_answers']} lần gọi provider; quá hạn {v['expired']}; "
             f"EA nhận {v['ea_accepted']} / từ chối {v['ea_rejected']}",
             f"Nguồn: EA {m['by_source']['EA']}, Telegram {m['by_source']['TELEGRAM']}; provider "
             + (", ".join(f"{p} {n}" for p, n in m["by_provider"].items()) or "--"),
             "Cổng nâng AI:"] + [f"  {k}: {s}" for k, s in g.items()]
    return "\n".join(lines)


def run(root: Path, days: float, now: int | None = None) -> str:
    import ai_bridge
    now = int(time.time()) if now is None else now
    m = metrics(load_jsonl(root / "logs" / "ai_bridge.jsonl"), load_jsonl(root / "logs" / "audit.jsonl"),
                load_jsonl(root / "logs" / "ai_recommendations.jsonl"), now - int(days * 86400), now + 1)
    g = gates(m, set(ai_bridge.ACTION_WHITELIST), ai_bridge.DEFAULT_CONFIG.get("circuit_failures", 0) > 0)
    return report_text(m, g)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--days", type=float, default=7)
    args = parser.parse_args(argv)
    print(run(Path(args.queue_root), args.days))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
