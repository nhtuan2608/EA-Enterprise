"""G66 D4 - offline loss-guard drill (LIVE-03). Read-only on the live files; never writes there.

Runs staged losses through the Python oracles of the risk kernel and asks whether ONE more trade of the
current per-trade risk would be allowed:
  * ftmo_headroom_oracle.calculate       (Risk/FtmoHeadroom.mqh)        CUSTOM floors + safety buffer
  * account_risk_ledger_oracle           (Risk/AccountRiskLedger.mqh)   open (remaining) risk reduces headroom
  * dry_run_gate comparison              (Risk/DryRunCandidateGate.mqh) existing_stress + projected <= available
                                         (only that one comparison is ported; the full gate needs a whole fixture)
  * internal_loss_room() below           PORT of EEA_ControlledLiveInternalLossRoom (no Python oracle exists)

EXPECTED RULE (written before any computation, see expected_allowed):
  internal: blocked when realized_today + open + next > daily(2%)  or  week_loss + open + next > weekly(4%)
  floors  : blocked when day_total + open + next >= CUSTOM daily 5% - buffer 0.5%
            or total_loss + open + next >= CUSTOM overall 10% - buffer 0.5%
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tests"))
from account_risk_ledger_oracle import apply_snapshot, defaults as ledger_defaults  # noqa: E402
from ftmo_headroom_oracle import calculate as headroom_calculate  # noqa: E402

LIVE = Path(r"C:\Users\Zbook Studio\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
            r"\MQL5\Files\EnterpriseEA\current")
EPS = 1e-9
CUSTOM_DAILY, CUSTOM_OVERALL = 5.0, 10.0

# (name, loss before this week %, loss earlier this week %, realized today %)
SCENARIOS = [
    ("Lo ngay 0%", 0, 0, 0), ("Lo ngay 1%", 0, 0, 1.0), ("Lo ngay 1.5%", 0, 0, 1.5),
    ("Lo ngay 1.9%", 0, 0, 1.9), ("Lo ngay 2.0%", 0, 0, 2.0), ("Lo ngay 2.5%", 0, 0, 2.5),
    ("Lo tuan 3% (cac ngay truoc)", 0, 3.0, 0), ("Lo tuan 3.9% (cac ngay truoc)", 0, 3.9, 0),
    ("Lo tuan 4% (cac ngay truoc)", 0, 4.0, 0),
    ("Gan san ngay CUSTOM 4.6%", 0, 0, 4.6), ("Gan san tong CUSTOM 9.6%", 9.6, 0, 0),
]


def load_inputs(live_dir: Path) -> dict:
    ledger = json.loads((live_dir / "risk_ledger.json").read_text(encoding="utf-8"))
    status = json.loads((live_dir / "live_status.json").read_text(encoding="utf-8"))
    acct = json.loads((live_dir / "account_snapshot.json").read_text(encoding="utf-8"))
    r = status["risk"]
    return {"initial": float(ledger["initial_capital"]), "reset_balance": float(ledger["last_reset_balance"]),
            "high_water": float(ledger["high_water_balance"]), "reset_utc": int(ledger["last_reset_utc"]),
            "daily_pct": float(r["daily_percent"]), "weekly_pct": float(r["weekly_percent"]),
            "open_pct": float(r["open_percent"]), "per_trade_pct": float(r["per_trade_percent"]),
            "next_pct": float(r.get("S06B_percent", r["per_trade_percent"])),
            "balance": float(acct["balance"]), "equity": float(acct["equity"])}


def expected_allowed(inp: dict, older: float, prior_week: float, today: float, open_pct: float) -> bool:
    """Written down BEFORE the oracles run. All values are percent of initial capital."""
    nxt, buf = inp["next_pct"], inp["per_trade_pct"]
    week = prior_week + today
    if today + open_pct + nxt > inp["daily_pct"] + EPS:
        return False
    if week + open_pct + nxt > inp["weekly_pct"] + EPS:
        return False
    if today + open_pct + nxt >= CUSTOM_DAILY - buf - EPS:
        return False
    if older + week + open_pct + nxt >= CUSTOM_OVERALL - buf - EPS:
        return False
    return True


def internal_loss_room(inp: dict, day_ref: float, week_balance: float, equity: float, open_money: float) -> dict:
    """PORT of EEA_ControlledLiveInternalLossRoom (Integration/ControlledLiveRuntime.mqh) plus the caps of
    EEA_ControlledLiveResolveV1Plan: per_trade_cap=min(per_trade, loss_room); portfolio cap = total_open - existing."""
    init = inp["initial"]
    daily_room = inp["daily_pct"] / 100 * init - (day_ref - equity)
    if daily_room <= 0:
        return {"allowed_money": 0.0, "reason": "INTERNAL_DAILY_LOSS_LIMIT_REACHED"}
    weekly_room = inp["weekly_pct"] / 100 * init - (week_balance - equity)
    if weekly_room <= 0:
        return {"allowed_money": 0.0, "reason": "INTERNAL_WEEKLY_LOSS_LIMIT_REACHED"}
    cap = min(inp["next_pct"] / 100 * init, min(daily_room, weekly_room))
    cap = min(cap, max(0.0, inp["open_pct"] / 100 * init - open_money))
    return {"allowed_money": max(cap, 0.0), "reason": "INTERNAL_LOSS_ROOM_AVAILABLE"}


def floor_check(inp: dict, day_ref: float, equity: float, open_money: float, next_money: float) -> tuple[bool, str]:
    init = inp["initial"]
    policy = {"status": "ACTIVE", "policy_id": "CUSTOM", "config_version": "v1", "source_version": "v1",
              "source_reference": "drill", "policy_timezone": "Europe/Prague", "account_currency": "USD",
              "initial_capital": init, "safety_buffer_money": inp["per_trade_pct"] / 100 * init,
              "custom_rules": {"daily_percent": CUSTOM_DAILY, "overall_percent": CUSTOM_OVERALL,
                               "trailing": False, "daily_from_equity": False}}
    data = {"daily_snapshot_valid": True, "daily_snapshot_quality": "OK", "reset_window_confirmed_by_caller": True,
            "daily_reset_at_utc": inp["reset_utc"], "daily_snapshot_id": "drill", "daily_snapshot_config_version": "v1",
            "daily_snapshot_currency": "USD", "balance_at_daily_reset": day_ref, "current_balance": equity,
            "floating_pnl_after_costs": 0.0, "proposed_stress_loss": open_money + next_money,
            "stress_loss_currency": "USD", "high_water_snapshot_valid": False, "high_water_snapshot_quality": "OK",
            "high_water_config_version": "v1", "high_water_as_of_utc": 0, "prior_overall_high_water_balance": init}
    # stress = open + next: the dry-run gate adds existing stress to the projected loss of the new trade.
    h = headroom_calculate(policy, data)
    if not h["valid"]:
        return False, h["reason_code"]
    snap = {"config_version": "v1", "account_id": "drill", "broker_server": "drill", "account_currency": "USD",
            "account_mode": "HEDGING", "data_quality": "OK", "reconciliation_status": "RECONCILED",
            "account_scope": "ACCOUNT_WIDE", "event_id": "e1", "source_snapshot_id": "s1", "positions_snapshot_id": "p1",
            "orders_snapshot_id": "o1", "deals_snapshot_id": "d1", "policy_snapshot_id": "pol1", "captured_at_utc": 100,
            "max_age_seconds": 300, "event_sequence": 1, "deal_watermark": 0, "positions_complete": True,
            "orders_complete": True, "deals_complete": True, "manual_activity_included": True,
            "other_ea_activity_included": True, "cash_flows_reconciled": True, "costs_reconciled": True,
            "account_mode_reconciled": True, "policy_headroom_valid": True, "policy_config_version": "v1",
            "policy_currency": "USD", "policy_quality": "OK", "equity_after_costs": equity,
            "equity_floor_headroom_money": h["available_headroom"], "content_fingerprint": "drill"}
    positions = []
    if open_money > 0:
        positions = [{"position_id": "p1", "origin": "EA", "canonical_symbol": "EURUSD", "broker_symbol": "EURUSD",
                      "direction": "LONG", "config_version": "v1", "account_currency": "USD", "volume": 0.1,
                      "initial_risk_money": open_money, "projected_loss_to_sl": open_money,
                      "remaining_loss_to_sl": open_money, "floating_pnl_after_costs": 0.0, "locked_profit_money": 0.0,
                      "risk_lineage_valid": True}]
    led = ledger_defaults()
    if not apply_snapshot(led, snap, positions, [], [], 120):
        return False, led["reason_code"]
    after = led["floor_headroom_after_ledger_risk_money"]
    gate_ok = open_money + next_money <= h["available_headroom"] - EPS  # DryRunCandidateGate stress comparison
    ok = (h["headroom_status"] == "SUFFICIENT" and gate_ok and not led["new_entries_blocked"]
          and after - next_money > EPS)
    return ok, h["headroom_status"]


def run(inp: dict) -> list[dict]:
    init = inp["initial"]
    rows = []
    for with_open in (False, True):
        for name, older, wk, today in SCENARIOS:
            open_pct = inp["next_pct"] if with_open else 0.0  # one open trade at the current per-trade risk
            next_money, open_money = inp["next_pct"] / 100 * init, open_pct / 100 * init
            week_balance = inp["reset_balance"] - older / 100 * init
            day_ref = week_balance - wk / 100 * init
            equity = day_ref - today / 100 * init
            exp = expected_allowed(inp, older, wk, today, open_pct)
            internal = internal_loss_room(inp, day_ref, week_balance, equity, open_money)
            full_internal = internal["allowed_money"] + EPS >= next_money
            floor_ok, note = floor_check(inp, day_ref, equity, open_money, next_money)
            if not full_internal and internal["allowed_money"] > EPS:
                note += f"; MQL giam lenh con {internal['allowed_money'] / init * 100:.2f}%"
            elif not full_internal:
                note += f"; {internal['reason']}"
            got = full_internal and floor_ok
            rows.append({"scenario": name + (" + 1 lenh mo 0.5%" if with_open else ""), "expected": exp,
                         "oracle": got, "note": note, "pass": exp == got})
    return rows


def render(rows: list[dict], inp: dict) -> str:
    def v(b):
        return "CHO PHEP" if b else "CHAN"
    out = ["# G66 D4 - Bai chan lo ngay/tuan (offline)\n",
           f"Von dau {inp['initial']:.2f}, so du reset {inp['reset_balance']:.2f}, dinh {inp['high_water']:.2f}; "
           f"tai khoan: balance {inp['balance']:.2f}, equity {inp['equity']:.2f}. Gioi han noi bo: ngay {inp['daily_pct']}%, "
           f"tuan {inp['weekly_pct']}%, mo {inp['open_pct']}%, moi lenh {inp['next_pct']}%. "
           f"San CUSTOM: ngay {CUSTOM_DAILY}%, tong {CUSTOM_OVERALL}%.\n",
           "| Kich ban | Ky vong | Oracle | Ghi chu | Ket qua |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['scenario']} | {v(r['expected'])} | {v(r['oracle'])} | {r['note']} | "
                   f"{'PASS' if r['pass'] else 'FAIL'} |")
    out.append(f"\nTong: {sum(r['pass'] for r in rows)}/{len(rows)} PASS")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-dir", type=Path, default=LIVE)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "loss_guard_drill.md")
    a = ap.parse_args(argv)
    inp = load_inputs(a.live_dir)
    rows = run(inp)
    text = render(rows, inp)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if all(r["pass"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
