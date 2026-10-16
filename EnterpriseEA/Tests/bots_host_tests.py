"""Bots host (design docs/superpowers/specs/2026-10-16-bots-host-design.md): Active flags, portfolio guard,
VHedge port, S07 gate, panel tab and Telegram command contract."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8-sig")


def body(src, signature):
    i = src.index(signature)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
    raise AssertionError("unbalanced " + signature)


class BotStateTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/BotState.mqh")

    def test_registry(self):
        for code in ("S07", "VHEDGE", "XRT", "CTXLIMIT"):
            self.assertIn(f'return "{code}";', self.src)
        self.assertIn("#define EEA_BOT_COUNT 4", self.src)

    def test_active_fails_closed_until_loaded(self):
        b = body(self.src, "bool EEA_BotActive(const int id)")
        self.assertIn("g_bots_state.loaded && g_bots_state.active[id]", b)
        d = body(self.src, "void EEA_BotsStateDefaults(EEA_BotsState &s)")
        self.assertIn("s.active[i]=false", d)

    def test_s07_gate_only_when_the_layer_runs(self):
        b = body(self.src, "bool EEA_BotS07EntriesAllowed()")
        self.assertIn("!g_bots_layer_enabled || (g_bots_state.loaded && g_bots_state.active[EEA_BOT_S07])", b)

    def test_load_bootstrap_and_fail_closed(self):
        b = body(self.src, "void EEA_BotsStateLoad(")
        self.assertIn("s.active[i]=defaults[i]", b)                      # missing file: input flags
        self.assertIn('"BOTS_STATE_UNREADABLE"', b)
        self.assertIn('"BOTS_STATE_IDENTITY_MISMATCH"', b)
        self.assertIn("s.active[i]=false;            // fail closed", b)
        self.assertIn('"BOTS_STATE_FAIL_CLOSED"', b)

    def test_commit_then_apply(self):
        b = body(self.src, "bool EEA_BotsSetActive(")
        save = b.index("EEA_BotsStateSave(next,root,reason)")
        adopt = b.index("s=next;")
        self.assertLess(save, adopt)
        self.assertIn('reason="BOTS_STATE_COMMIT_FAILED"; return false;', b)

    def test_aliases(self):
        b = body(self.src, "int EEA_BotFind(const string name)")
        for alias in ('"G119"', '"XRT"', '"CTX"', '"S07"', '"HEDGE"'):
            self.assertIn(alias, b)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/PortfolioGuard.mqh")

    def test_guard_order_and_codes(self):
        b = body(self.src, "string EEA_BotGuardCheck(")
        codes = ['"BOTS_GUARD_NOT_READY"', '"BOT_INACTIVE"', '"EA_EXECUTION_NOT_ARMED"', '"OPERATOR_PAUSED_ENTRIES"',
                 '"BOTS_CAPITAL_UNKNOWN"', '"BOTS_DAILY_LOSS_LIMIT"', '"BOTS_OPEN_RISK_CAP"']
        pos = [b.index(c) for c in codes]
        self.assertEqual(pos, sorted(pos))
        self.assertIn("if(require_active && !EEA_BotActive(bot))", b)

    def test_open_risk_is_account_wide_and_fails_closed(self):
        b = body(self.src, "bool EEA_BotsAccountOpenRisk(")
        self.assertIn("PositionsTotal()", b)
        self.assertIn("OrdersTotal()", b)
        self.assertNotIn("POSITION_MAGIC", b)                            # every magic counts
        self.assertIn('"BOTS_POSITION_WITHOUT_STOP"', b)
        self.assertIn('"BOTS_ORDER_WITHOUT_STOP"', b)

    def test_defaults_block(self):
        b = body(self.src, "void EEA_BotGuardDefaults(")
        self.assertIn("g.ready=false", b)
        self.assertIn("g.operator_paused=true", b)
        self.assertIn("g.execution_live=false", b)


class VHedgeBotTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/VHedgeBot.mqh")
        self.tester = read("VHedgeTester.mq5")

    def test_defaults_are_g119_only(self):
        b = body(self.src, "void VHedgeBotParamsDefaults(")
        for token in ("p.prof_g119=true", "p.prof_bigv=false", "p.stop_g119=1.5", "p.stop_bigv=1.0", "p.ema_spread_atr=0.91",
                      "p.v_vol_ratio=1.26", "p.r_vol_ratio=1.17", "p.bigv_size_atr=1.38", "p.target_r=5.0",
                      "p.break_even=true", "p.risk_percent=0.75", "p.magic=116119", "p.mode=BOT_SHADOW"):
            self.assertIn(token, b)

    def test_rules_are_the_tester_rules(self):
        self.assertIn("#define VHB_RET_BARS 6", self.src)
        self.assertIn("#define VHB_CAP_BARS 288", self.src)
        for token in ("(r[i].open<e[i] && r[i].close>e[i]) || (r[i].open>e[i] && r[i].close<e[i])",
                      "if(inside) { decided=true; hit=(left && q==j); }", "if(hit && found_v<0) found_v=v;",
                      "const double gap=(stop_atr+0.1)*atr;", "G.tp=G.surv_entry+d*p.target_r*G.R;",
                      "A.entry=(d==1 ? ask : bid);", "A.sl=G.surv_sl"):
            self.assertIn(token, self.src)

    def test_new_group_asks_the_guard_and_the_flag(self):
        b = body(self.src, "bool OpenGroup(")
        self.assertIn("if(!EEA_BotActive(EEA_BOT_VHEDGE))", b)
        self.assertIn('EEA_BotGuardCheck(EEA_BOT_VHEDGE,2.0*leg_risk,"SCALP",true,p.news_guard)', b)
        self.assertLess(b.index("EEA_BotGuardCheck"), b.index("LiveOpen("))

    def test_add_is_a_guarded_risk_increase_without_the_active_check(self):
        b = body(self.src, "void ManageGroup(")
        self.assertIn('EEA_BotGuardCheck(EEA_BOT_VHEDGE,-add_risk,"SCALP",false,false)', b)
        self.assertLess(b.index("EEA_BotGuardCheck"), b.index('StringFormat("VH%d %s A"'))

    def test_live_needs_hedging_and_groups_persist(self):
        b = body(self.src, "void Init(")
        self.assertIn("ACCOUNT_MARGIN_MODE_RETAIL_HEDGING", b)
        self.assertIn('"VHEDGE_LIVE_NEEDS_HEDGING_ACCOUNT"', b)
        self.assertIn("Load();", b)
        self.assertIn('return root+"/current/bots/vhedge_groups.txt";', self.src)
        tick = body(self.src, "void OnTick()")
        self.assertIn("if(dirty) Save();", tick)

    def test_management_runs_for_inactive_bots(self):
        tick = body(self.src, "void OnTick()")
        self.assertNotIn("EEA_BotActive", tick)                          # Inactive only stops new groups


class HostTests(unittest.TestCase):
    def setUp(self):
        self.host = read("Bots/BotHost.mqh")
        self.ea = read("EnterpriseEA.mq5")
        self.cl = read("Integration/ControlledLiveRuntime.mqh")

    def test_s07_gate_in_the_entry_check(self):
        b = body(self.cl, "bool EEA_S07EntryAllowed(")
        self.assertIn('if(!EEA_BotS07EntriesAllowed()) { reason="S07_BOT_INACTIVE"; return false; }', b)
        self.assertLess(b.index("EEA_BotS07EntriesAllowed"), b.index("EEA_S07OpenLegs"))

    def test_command_contract(self):
        b = body(self.host, "string EEA_BotCommandEvaluate(")
        for token in ('"OPERATOR"', '"private_chat_attested"', '"sender_authenticated"', '"source_authenticated"',
                      "s.account_id", "s.config_version", "now>expires", "s.last_gateway_sequence",
                      '"BOT_COMMAND_ALREADY_COMMITTED"'):
            self.assertIn(token, b)
        dis = b.index('if(action=="BOT_DISABLE") return "";')
        req = b.index('if(action=="BOT_REQUEST_ENABLE")')
        self.assertLess(dis, req)                                         # a disable needs no nonce
        confirm = b[b.index('if(action=="BOT_CONFIRM_ENABLE")'):]
        for token in ("s.pending_bot!=bot", "nonce!=s.pending_nonce", "chat!=s.pending_chat_id",
                      "user!=s.pending_user_id", "now>s.pending_expires_at_utc"):
            self.assertIn(token, confirm)
        self.assertIn("#define EEA_BOT_MAX_NONCE_SECONDS 120", self.host)

    def test_results_are_one_file_per_command(self):
        b = body(self.host, "void EEA_BotsProcessCommands(")
        self.assertIn('"/current/remote/results/"+command_id+".json"', b)
        self.assertIn("FileDelete(path,0);", b)

    def test_shell_wiring(self):
        tick = body(self.ea, "void OnTick()")
        self.assertIn("if(InpBotsEnabled) EEA_BotsHostTick();", tick)
        code = re.sub(r"//.*", "", tick)
        self.assertEqual(len(re.findall(r";", code)), 1)                 # nothing else on the tick
        self.assertIn("EEA_BotsGuardUpdate();", self.ea)
        self.assertIn("EEA_BotsHostTimer(g_runtime.account.account_fingerprint,g_config.config_version,g_audit);", self.ea)
        self.assertIn("EEA_BotsHostDeinit();", self.ea)
        g = body(self.ea, "void EEA_BotsGuardUpdate()")
        for token in ("g_live_config.enabled && g_live_config.armed", "!g_live_runtime.recovery_blocked",
                      "!g_controller.kill_active", "EEA_RemoteEntriesPaused()", 'EEA_LiveSessionStateText(session_reason)=="ACTIVE"'):
            self.assertIn(token, g)

    def test_inputs(self):
        for token in ("input bool   InpBotsEnabled", "input EEA_BotModeInput InpBotVHedgeMode = BOT_SHADOW;",
                      "input double InpBotVHedgeRiskPct        = 0.75;", "input bool   InpBotVHedgeBigV           = false;",
                      "input double InpBotsMaxOpenRiskPct", "input double InpBotsDailyLossPct",
                      "input bool   InpBotsRequireLiveSession  = true;"):
            self.assertIn(token, self.ea)


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Runtime/SymbolSelectionPanel.mqh")

    def test_bots_tab(self):
        self.assertIn('string tabs[5]={"RISK","SYMBOLS","AUTHORIZATION","SYSTEM","BOTS"};', self.src)
        self.assertIn('settings=="BOTS"', self.src)

    def test_turning_on_needs_a_second_click(self):
        i = self.src.index('StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Btn_Bot_")==0')
        handler = self.src[i:i + 900]
        self.assertIn("if(active || EEA_SymbolPanelBotConfirming(code))", handler)
        self.assertIn("g_panel_state.bot_confirm_tick=GetTickCount();", handler)
        b = body(self.src, "bool EEA_SymbolPanelBotConfirming(")
        self.assertIn("<10000", b)



class BotJournalTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/BotJournal.mqh")

    def test_monthly_append_only_file(self):
        self.assertIn('StringFormat("bots-%04d%02d.jsonl",t.year,t.mon)', self.src)
        log = body(self.src, "void EEA_BotLog(")
        self.assertIn("EEA_WriteAtomicAppendText(EEA_BotJournalPath(now),line+\"\\n\");", log)
        for key in ("at_utc", "server", "bot", "event", "mode", "text", "data"):
            self.assertIn(f'\\"{key}\\":', log)
        self.assertIn('if(g_bot_journal_root=="") return;', log)

    def test_blocked_only_when_the_reason_changes(self):
        blk = body(self.src, "void EEA_BotLogBlock(")
        self.assertIn("if(g_bot_journal_block[bot]==reason) return;", blk)
        self.assertIn('EEA_BotLog(bot,"BLOCKED"', blk)
        self.assertIn('#include "BotJournal.mqh"', read("Bots/PortfolioGuard.mqh"))

    def test_hooks_in_every_bot(self):
        vh, xrt, ctx, host = (read("Bots/VHedgeBot.mqh"), read("Bots/XrtBot.mqh"), read("Bots/CtxLimitBot.mqh"),
                              read("Bots/BotHost.mqh"))
        for ev in ('"SKIP"', '"ENTRY"', '"MANAGE"', '"EXIT"'):
            self.assertIn(f"EEA_BotLog(EEA_BOT_VHEDGE,{ev}", vh)
        self.assertIn("EEA_BotLogBlock(EEA_BOT_VHEDGE,ModeText(),pv_block,desc);", vh)
        for ev in ('"DECISION"', '"EXIT"', '"SKIP"'):
            self.assertIn(f"EEA_BotLog(EEA_BOT_XRT,{ev}", xrt)
        self.assertIn("EEA_BotLogBlock(EEA_BOT_XRT,", xrt)
        decide = body(ctx, "void Decide(const datetime bar_time)")
        self.assertIn("DecideCore(bar_time);", decide)
        self.assertIn('"DECISION"', decide)
        self.assertIn('EEA_BotLog(EEA_BOT_CTXLIMIT,"EXIT","SHADOW"', ctx)
        self.assertIn("g_bot_journal_root=root;", body(host, "void EEA_BotsHostInit("))
        timer = body(host, "void EEA_BotsHostTimer(")
        self.assertIn("EEA_BotsJournalNear(); EEA_BotsJournalDeals();", timer)
        self.assertIn('"SWITCH"', body(host, "bool EEA_BotsPanelToggle("))
        self.assertIn('"TELEGRAM"', body(host, "void EEA_BotsProcessCommands("))

    def test_live_deals_are_journaled_once(self):
        deals = body(read("Bots/BotHost.mqh"), "void EEA_BotsJournalDeals()")
        self.assertIn("if(first) continue;", deals)          # a restart does not repeat old deals
        self.assertIn("d<=g_bot_deal_seen", deals)
        self.assertIn("EEA_BotByMagic(HistoryDealGetInteger(d,DEAL_MAGIC))", deals)
        self.assertIn('in ? "FILL" : "CLOSE"', deals)


if __name__ == "__main__":
    unittest.main()


class XrtBotTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/XrtBot.mqh")
        self.tester = read("XauRegimeTester.mq5")

    def test_defaults_match_the_tester_set(self):
        b = body(self.src, "void XrtBotParamsDefaults(")
        for token in ("p.risk_percent=1.5", "p.dir_mode=XRB_LONG_ONLY", "p.ema_period=50", "p.slope_days=10",
                      "p.atr_period=20", "p.buy_zone=XRB_MARKET", "p.stop_atr=3.0", "p.trail=true", "p.trail_atr=3.0",
                      "p.magic=969696", "p.mode=BOT_SHADOW"):
            self.assertIn(token, b)
        self.assertIn("#define XRB_MAX_CHASE_ATR 0.5", self.src)
        self.assertIn("#define XRT_MAX_CHASE_ATR 0.5", self.tester)

    def test_regime_and_exits_are_the_tester_rules(self):
        for token in ("day.state=(side==slope ? side : 0);", "plan.stop=base-dir*p.stop_atr*day.atr;",
                      "if(day.state!=dir) { CloseOwn(", "dir*(day.close-best)<=-p.trail_atr*day.atr",
                      "if(blocked_dir!=0 && day.state!=blocked_dir) blocked_dir=0;"):
            self.assertIn(token, self.src)
        for token in ("g_day.state=(side==slope ? side : 0);", "g_plan.stop=base-dir*InpStopAtr*g_day.atr;"):
            self.assertIn(token, self.tester)

    def test_gates_use_the_live_ea_and_the_guard(self):
        b = body(self.src, "double EntryGate(")
        self.assertIn("g_bot_guard.news_block_swing", b)
        self.assertIn("g_bot_guard.sent_block[k]", b)
        self.assertIn('EEA_BotGuardCheck(EEA_BOT_XRT,risk_money*sent,"SWING",true,false)', b)
        self.assertIn('else if(!EEA_BotActive(EEA_BOT_XRT))', b)

    def test_state_persists(self):
        self.assertIn('return root+"/current/bots/xrt_state.txt";', self.src)
        self.assertIn("Load();", body(self.src, "void Init("))


class CtxLimitBotTests(unittest.TestCase):
    def setUp(self):
        self.src = read("Bots/CtxLimitBot.mqh")
        self.tester = read("CtxLimitTester.mq5")

    def test_defaults_and_threshold(self):
        b = body(self.src, "void CtxLimitBotParamsDefaults(")
        for token in ("p.plan=CTXB_PLAN_LIMIT", "p.risk_percent=0.5", "p.unordered_weight=0.67", "p.stop_atr=1.0",
                      "p.target_atr=2.0", "p.pull_atr=0.5", "p.limit_bars=8", "p.hold_bars=96", "p.magic=717171"):
            self.assertIn(token, b)
        self.assertIn("0.3825820347356539 : 0.21075521107935286", self.src)
        self.assertIn("0.3825820347356539 : 0.21075521107935286", self.tester)

    def test_features_are_the_tester_features(self):
        strip = lambda x: re.sub(r"\s+", "", re.sub(r"//.*", "", x)).replace("Ctxb", "Ctx").replace("CTXB_", "CTX_")
        mine = strip(body(self.src, "void CtxAdd(const MqlRates &r)"))
        theirs = strip(body(self.tester, "void CtxAdd(const MqlRates &r)"))
        mine = mine.replace("dday", "day").replace("constdoubleh=r.high", "constdoubleo=r.open,h=r.high")
        self.assertEqual(mine, theirs)

    def test_new_order_asks_the_guard(self):
        b = body(self.src, "void DecideCore(")
        self.assertIn('EEA_BotGuardCheck(EEA_BOT_CTXLIMIT,risk_money,"SWING",true,false)', b)
        self.assertLess(b.index("EEA_BotGuardCheck"), b.index("trade.Buy("))
        self.assertIn("if(!EEA_BotActive(EEA_BOT_CTXLIMIT))", b)


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        self.ea = read("EnterpriseEA.mq5")

    def test_second_instance_is_refused_with_a_message(self):
        init = body(self.ea, "int OnInit()")
        self.assertLess(init.index("EEA_InstanceClaim(instance_message)"), init.index("EAConfig_LoadDefaults(g_config)"))
        self.assertIn("Alert(instance_message);", init)
        claim = body(self.ea, "bool EEA_InstanceClaim(string &message)")
        self.assertIn("chart!=EEA_InstanceChartTag() && age>=0 && age<EEA_InstanceMaxAge()", claim)
        self.assertIn("MQL_TESTER", claim)
        self.assertIn("Only one EnterpriseEA per data root", claim)
        self.assertIn('"INIT_FAILED: cannot open MQL5', init)

    def test_stamp_and_release(self):
        self.assertIn("EEA_InstanceBeat();", body(self.ea, "void OnTimer()"))
        self.assertIn("EEA_InstanceRelease();", body(self.ea, "void OnDeinit(const int reason)"))
        rel = body(self.ea, "void EEA_InstanceRelease()")
        self.assertIn('GlobalVariableGet(k+"_chart")==EEA_InstanceChartTag()', rel)   # only its own stamp


class PolicyConfirmTests(unittest.TestCase):
    def test_confirming_the_policy_in_force_is_saved_at_once(self):
        src = read("Runtime/SymbolSelectionPanel.mqh")
        i = src.index('if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_ConfirmPolicy")')
        handler = src[i:i + 1500]
        self.assertIn("g_panel_state.staged_policy==g_panel_state.committed_policy", handler)
        self.assertIn("EEA_SymbolPanelPersistPolicy(ctx,audit,false)", handler)
        self.assertIn("g_panel_state.policy_confirmed=!g_panel_state.policy_confirmed;\n            g_panel_state.apply_reason",
                      handler.replace("\r\n", "\n"))                    # a failed write rolls the toggle back


class PolicyReclickTests(unittest.TestCase):
    def test_clicking_the_policy_in_force_keeps_the_confirmation(self):
        src = read("Runtime/SymbolSelectionPanel.mqh")
        guard = src.index('if(StringFind(sparam,EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_")==0)')
        first = src.index('if(sparam==EEA_PANEL_OVERLAY_PREFIX+"Btn_Policy_FTMO_1_STEP")')
        self.assertLess(guard, first)
        self.assertIn("pick==g_panel_state.staged_policy && pick==g_panel_state.committed_policy", src[guard:first])


class MiniPanelTests(unittest.TestCase):
    def test_collapsed_panel_shows_every_bot_and_the_closest(self):
        src = read("Runtime/SymbolSelectionPanel.mqh")
        self.assertTrue((ROOT / "Runtime/SymbolSelectionPanel.mqh").read_bytes().startswith(b"\xef\xbb\xbf"))
        mini = body(src, "void EEA_SymbolPanelRenderMiniBots(const long chart_id)")
        self.assertIn("near_score>g_panel_bots[best].near_score", body(src, "int EEA_SymbolPanelMiniBest()"))
        self.assertIn("Gần khớp nhất", body(src, "string EEA_SymbolPanelMiniBestText()"))
        self.assertIn("EEA_SymbolPanelRenderMiniBots(chart_id);", body(src, "void EEA_SymbolPanelRenderMainView("))
        self.assertIn("EEA_SymbolPanelMiniLineCount()*EEA_PANEL_MINI_LINE", body(src, "int EEA_SymbolPanelHeight()"))
        self.assertIn("OBJPROP_TOOLTIP", mini)

    def test_closeness_sources(self):
        host = read("Bots/BotHost.mqh")
        s07 = body(host, "void EEA_BotsS07Near(const string sym)")
        for token in ("EEA_S07_ADX_LOW", "EEA_S07_DI_GAP", "EEA_S07_ADX_RISE", "EEA_S07WindowBars(\"M30\")", "g_bot_s07_near=best_n/5.0;"):
            self.assertIn(token, s07)
        near = body(host, "void EEA_BotNear(const int id,double &score,string &text)")
        self.assertIn("if(!EEA_BotActive(id)) score=0.0;", near)
        self.assertIn('\\"near\\":', host)
        self.assertRegex(read("Bots/VHedgeBot.mqh"), r"double\s+near_score;")
        self.assertIn("void Near(double &score,string &text)", read("Bots/XrtBot.mqh"))
        self.assertIn("void Near(double &score,string &text) const", read("Bots/CtxLimitBot.mqh"))
