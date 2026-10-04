"""Account auto profile, durable state and restore checks (plan step 4 and restore).

Reference oracles mirror Runtime/AccountAutoProfile.mqh, Storage/DailyStatsStore.mqh
and Storage/RiskLedgerStore.mqh. Design evidence only, not MQL5 runtime proof.
"""
from __future__ import annotations

import calendar
import datetime as dt
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


def ts(*args) -> int:
    return int(dt.datetime(*args, tzinfo=UTC).timestamp())


def last_sunday_utc(year: int, month: int) -> int:
    last = calendar.monthrange(year, month)[1]
    day = dt.date(year, month, last)
    while day.weekday() != 6:
        day -= dt.timedelta(days=1)
    return ts(day.year, day.month, day.day)


def prague_offset(utc: int) -> int:
    year = dt.datetime.fromtimestamp(utc, UTC).year
    start = last_sunday_utc(year, 3) + 3600
    end = last_sunday_utc(year, 10) + 3600
    return 7200 if start <= utc < end else 3600


def prague_reset(now: int) -> int:
    local = now + prague_offset(now)
    midnight = (local // 86400) * 86400
    guess = midnight - prague_offset(now)
    return midnight - prague_offset(guess)


def balance_at(deals, current_balance, at):
    return current_balance - sum(d["net"] for d in deals if d["time"] >= at)


def exposure_allows(existing, base, quote, direction, risk, cap, max_correlated):
    after = {k: list(v) for k, v in existing.items()}

    def add(cur, signed):
        risk_total, contributors = after.get(cur, [0.0, 0])
        if risk_total == 0.0 or (risk_total > 0) == (signed > 0):
            contributors += 1
        after[cur] = [risk_total + signed, contributors]

    add(base, direction * risk)
    add(quote, -direction * risk)
    for cur in (base, quote):
        if abs(after[cur][0]) > cap + 1e-9:
            return False, "CURRENCY_EXPOSURE_CAP_" + cur
        if after[cur][1] > max_correlated:
            return False, "CORRELATED_TRADES_LIMIT_" + cur
    return True, "CURRENCY_EXPOSURE_OK"


class PragueResetTests(unittest.TestCase):
    def test_summer_winter_and_dst_switch_days(self):
        self.assertEqual(prague_reset(ts(2026, 10, 3, 12)), ts(2026, 10, 2, 22))   # CEST
        self.assertEqual(prague_reset(ts(2026, 12, 1, 12)), ts(2026, 11, 30, 23))  # CET
        self.assertEqual(prague_reset(ts(2026, 10, 25, 12)), ts(2026, 10, 24, 22))  # day summer time ends
        self.assertEqual(prague_reset(ts(2026, 3, 29, 12)), ts(2026, 3, 28, 23))    # day summer time starts
        self.assertEqual(prague_reset(ts(2026, 10, 2, 22)), ts(2026, 10, 2, 22))    # exactly at reset
        self.assertEqual(prague_reset(ts(2026, 10, 2, 21, 59)), ts(2026, 10, 1, 22))

    def test_matches_zoneinfo_when_available(self):
        try:
            from zoneinfo import ZoneInfo
            prague = ZoneInfo("Europe/Prague")
        except Exception:  # tzdata may be absent on Windows
            self.skipTest("zoneinfo data unavailable")
        for hours in range(0, 24 * 400, 7):
            now = ts(2026, 1, 1) + hours * 3600
            local = dt.datetime.fromtimestamp(now, prague)
            midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
            self.assertEqual(prague_reset(now), int(midnight.timestamp()), local)

    def test_mql_uses_eu_rule(self):
        src = (ROOT / "Runtime/AccountAutoProfile.mqh").read_text(encoding="utf-8")
        for token in ("EEA_AutoLastSundayUtc(dt.year,3)+3600", "EEA_AutoLastSundayUtc(dt.year,10)+3600",
                      "(last_day+4)%7", "return local_midnight-EEA_PragueOffsetSeconds(guess);"):
            self.assertIn(token, src)


class AccountProfileTests(unittest.TestCase):
    def test_balance_at_reset_unwinds_all_later_deals(self):
        deals = [{"time": 100, "net": 50.0}, {"time": 200, "net": -20.0}, {"time": 300, "net": 1000.0}]
        self.assertEqual(balance_at(deals, 10_000.0, 200), 10_000.0 + 20.0 - 1000.0)
        src = (ROOT / "Runtime/AccountAutoProfile.mqh").read_text(encoding="utf-8")
        body = src.split("bool EEA_BalanceAtUtc", 1)[1].split("double EEA_InitialCapitalFromHistory", 1)[0]
        self.assertIn("snapshot.history_from_utc>at_utc", body)
        self.assertIn('"BALANCE_HISTORY_INCOMPLETE"', body)
        self.assertNotIn('type!="0"', body)  # cash flows are part of the balance

    def test_currency_exposure_and_correlation_limits(self):
        cap, per = 1250.0, 500.0
        existing = {}
        ok, _ = exposure_allows(existing, "EUR", "USD", 1, per, cap, 2)
        self.assertTrue(ok)
        existing = {"EUR": [500.0, 1], "USD": [-500.0, 1], "GBP": [500.0, 1]}
        existing["USD"] = [-1000.0, 2]  # long EURUSD and long GBPUSD
        ok, reason = exposure_allows(existing, "AUD", "USD", 1, per, cap, 2)
        self.assertFalse(ok)
        self.assertEqual(reason, "CURRENCY_EXPOSURE_CAP_USD")
        ok, reason = exposure_allows({"USD": [-400.0, 2]}, "NZD", "USD", 1, 100.0, cap, 2)
        self.assertEqual(reason, "CORRELATED_TRADES_LIMIT_USD")
        src = (ROOT / "Runtime/AccountAutoProfile.mqh").read_text(encoding="utf-8")
        for token in ("EEA_CurrencyExposureAdd(e,base,direction*risk_money)", "EEA_CurrencyExposureAdd(e,quote,-direction*risk_money)",
                      "MathAbs(after.risk[i])>cap_money+1e-9", "after.contributors[i]>max_correlated"):
            self.assertIn(token, src)

    def test_costs_and_leverage_come_from_the_broker(self):
        src = (ROOT / "Runtime/AccountAutoProfile.mqh").read_text(encoding="utf-8")
        for token in ("MathAbs(snapshot.deals[i].commission)", "learned=volume>0.0", "rates[i].spread",
                      "SYMBOL_SWAP_MODE_POINTS", "SYMBOL_SWAP_LONG", "ACCOUNT_LEVERAGE", "DEAL_TYPE_BALANCE"):
            self.assertIn(token, src)
        self.assertNotIn("OrderSend", src)


class DurableStateTests(unittest.TestCase):
    def test_daily_stats_accumulate_and_only_recompute_covered_days(self):
        src = (ROOT / "Storage/DailyStatsStore.mqh").read_text(encoding="utf-8")
        merge = src.split("bool EEA_DailyStatsMerge", 1)[1].split("string EEA_DailyStatsPath", 1)[0]
        for token in ("(snapshot.history_from_utc+offset_seconds+86399)/86400",
                      'snapshot.deals[i].type!="0" && snapshot.deals[i].type!="1"',
                      "EEA_DailyStatsPut(book,fresh[d])", "EEA_DailyStatsRemove(book,fresh[d].day)"):
            self.assertIn(token, merge)
        load = src.split("bool EEA_DailyStatsLoad", 1)[1]
        self.assertIn('"\\"account_fingerprint\\":\\""+EEA_JsonEscape(account_fingerprint)', load)
        self.assertIn('"\\"utc_offset_seconds\\":"+IntegerToString(offset_seconds)', load)
        self.assertIn("EEA_WriteAtomicText", src)

    def test_risk_ledger_restores_capital_and_monotonic_high_water(self):
        src = (ROOT / "Storage/RiskLedgerStore.mqh").read_text(encoding="utf-8")
        for token in ("l.high_water_balance<l.initial_capital", "if(balance>hw) hw=balance;",
                      "EEA_PragueDailyResetUtc(now_utc)", "EEA_BalanceAtUtc(snapshot,current_balance,resets[k]",
                      "EEA_WriteAtomicText"):
            self.assertIn(token, src)
        shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        maintain = shell.split("void EEA_MaintainDurableState()", 1)[1].split("string EEA_PanelControllerStatusText", 1)[0]
        for token in ("EEA_DailyStatsLoad(root", "EEA_DailyStatsWrite(root", "EEA_RiskLedgerLoad(root",
                      "EEA_InitialCapitalFromHistory()", '"HISTORY_FIRST_DEPOSIT"', '"INPUT"', "EEA_RiskLedgerWrite(root"):
            self.assertIn(token, maintain)
        self.assertEqual(shell.count("EEA_MaintainDurableState();"), 2)

    def test_calendar_uses_stored_days_outside_history_window(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        calendar_src = panel.split("void EEA_SymbolPanelDashCalendar", 1)[1].split("void EEA_SymbolPanelRenderActiveView", 1)[0]
        self.assertIn("if(day_index>=loaded_from) continue;", calendar_src)
        self.assertIn("EEA_DailyStatsLookup(day_index,row)", calendar_src)
        self.assertIn("|| stored[day]", calendar_src)

    def test_panel_view_preferences_are_restored(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn("EEA_SymbolPanelLoadUiState(ctx.root);", panel)
        self.assertGreaterEqual(panel.count("EEA_SymbolPanelSaveUiState(ctx.root);"), 4)
        loader = panel.split("void EEA_SymbolPanelLoadUiState", 1)[1].split("void EEA_SymbolPanelRenderSettingsRows", 1)[0]
        self.assertIn('view=="DASHBOARD" || view=="SETTINGS"', loader)


if __name__ == "__main__":
    unittest.main()
