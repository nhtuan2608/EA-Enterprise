"""AI Bridge v1, EA side: queue, validation, circuit breaker, schedule, never trades."""
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def section(text, start, end_marker="\n  }\n"):
    return text.split(start, 1)[1].split(end_marker, 1)[0]


class AiClientTests(unittest.TestCase):
    def setUp(self):
        self.client = read("Runtime/AiBridgeClient.mqh")
        self.shell = read("EnterpriseEA.mq5")

    def test_enqueue_respects_limits(self):
        enqueue = section(self.client, "bool EEA_AiEnqueue")
        for token in ('"AI_DISABLED"', '"AI_CIRCUIT_OPEN"', '"AI_DAILY_LIMIT_REACHED"',
                      '"AI_REQUEST_ALREADY_PENDING"', '"AI_CONTEXT_TOO_LARGE"', '"AI_REQUEST_QUEUED"'):
            self.assertIn(token, enqueue)
        self.assertIn('/ai/requests/"+id+".json"', enqueue)

    def test_answers_are_revalidated(self):  # TC-AI-02 / TC-AI-04
        validate = section(self.client, "string EEA_AiValidate")
        for token in ('"AI_RESPONSE_SCHEMA_INVALID"', '"AI_RESPONSE_ID_MISMATCH"', '"AI_RESPONSE_TYPE_MISMATCH"',
                      '"AI_PROVIDER_MISMATCH"', '"AI_RESPONSE_EXPIRED"', '"AI_ACTION_NOT_ALLOWED"'):
            self.assertIn(token, validate)

    def test_timeouts_and_circuit(self):  # TC-AI-01 / TC-AI-06
        poll = section(self.client, "void EEA_AiPoll")
        self.assertIn("now>c.pending_deadline[k]", poll)
        self.assertIn('"AI_BRIDGE_OFFLINE"', poll)
        failure = section(self.client, "void EEA_AiFailure")
        self.assertIn("c.failures>=EEA_AI_CIRCUIT_FAILURES", failure)
        self.assertIn("#define EEA_AI_CIRCUIT_SECONDS 1800", self.client)

    def test_accepted_answers_are_stored_for_req012(self):
        poll = section(self.client, "void EEA_AiPoll")
        self.assertIn('/logs/ai_recommendations.jsonl"', poll)
        self.assertIn('/ai/reports/"+type+".json"', poll)

    def test_schedule_and_inputs(self):
        self.assertIn('input string InpAiNewsReviewLocal       = "07:00";', self.shell)
        self.assertIn('input string InpAiDiagnosticsLocal      = "06:30";', self.shell)
        self.assertIn("input int    InpAiMaxCallsPerDay        = 30;", self.shell)
        timer = section(self.shell, "void EEA_AiTimer")
        self.assertIn('EEA_AiEnqueueReport("NEWS_DATA_REVIEW",reason);', timer)
        self.assertIn('EEA_AiEnqueueReport("EA_DIAGNOSTICS",reason);', timer)
        self.assertIn('EEA_AiEnqueueReport("NEWS_EVENT_REVIEW",reason);', timer)
        enqueue = section(self.shell, "void EEA_AiEnqueueReport")
        self.assertIn('EEA_AiEnqueue(g_ai,g_audit,type,"codex"', enqueue)       # diagnostics go to codex

    def test_pre_news_brief_rule(self):  # REQ-007
        self.assertIn("input int    InpAiPreNewsMinutes        = 45;", self.shell)
        self.assertIn('if(i==4) return "NEWS_PRE_BRIEF";', self.client)
        self.assertIn("#define EEA_AI_TYPES 5", self.client)
        due = section(self.shell, "long EEA_AiPreBriefDue")
        self.assertIn("InpAiPreNewsMinutes<=0", due)                                   # 0 = off
        self.assertIn("now<t-(long)InpAiPreNewsMinutes*60 || now>t-300", due)           # [T-N min, T-5 min]
        self.assertIn("EEA_AiPreBriefDone(g_ai,t)", due)                                # once per cluster
        self.assertIn("g_news.events[e-1].time_utc==t", due)                            # one cluster per time_utc
        timer = section(self.shell, "void EEA_AiTimer")
        self.assertIn("EEA_AiPreBriefDue()", timer)
        self.assertIn('EEA_AiEnqueueReport("NEWS_PRE_BRIEF",reason);', timer)
        self.assertIn("EEA_AiPreBriefRemember(g_ai,g_ai_pre_brief_time); EEA_AiSaveState(g_ai);", timer)
        # remembered clusters survive a restart (persisted next to last_news_review_day), newest 32 kept
        self.assertIn("#define EEA_AI_PRE_BRIEF_KEEP 32", self.client)
        self.assertIn('\\"pre_brief_times\\":', section(self.client, "void EEA_AiSaveState"))
        self.assertIn('EEA_AiField(json,"pre_brief_times")', section(self.client, "void EEA_AiClientInit"))
        enqueue = section(self.shell, "void EEA_AiEnqueueReport")
        brief = enqueue.split('type=="NEWS_PRE_BRIEF"', 1)[1]
        self.assertIn('"[\\"REPORT\\",\\"WARN\\",\\"RECOMMEND_REVIEW\\"]"', brief)
        self.assertIn("EEA_AiAnalysisProvider()", brief)
        for forbidden in ("OPEN", "TRADE", "RECOMMEND_WINDOW_CHANGE", "EEA_Execution"):
            self.assertNotIn(forbidden, brief)

    def test_pre_news_context_fields(self):  # REQ-007
        body = section(self.shell, "string EEA_AiContextPreBrief")
        for token in ("minutes_to_release", "forecast", "previous", "news_state", "swing_block_from_utc",
                      "scalp_block_from_utc", "EEA_NewsReactionStatsForCluster(g_news_reaction", "median_move15_atr",
                      "p80_move60_atr", "reversal_rate", "median_recovery_min", "current_r", "break_even_rule",
                      "be_before_min", "be_min_r", "EEA_JsonEscape(g_news.events[e].name)"):
            self.assertIn(token, body)
        for forbidden in ("account_fingerprint", "ACCOUNT_LOGIN", "FileOpen", "logs/"):   # memory only, no log re-read
            self.assertNotIn(forbidden, body)

    def test_ai_never_reaches_orders(self):  # TC-AI-09
        for forbidden in ("OrderSend", "EEA_ExecutionSubmit", "EEA_ExecutionClosePosition",
                          "EEA_ExecutionModifyProtective", "base_risk_fraction"):
            self.assertNotIn(forbidden, self.client)
        for name in ("void EEA_AiTimer", "void EEA_AiHandlePanelRequest", "void EEA_AiEnqueueReport",
                     "string EEA_AiContextPreBrief", "long EEA_AiPreBriefDue"):
            body = section(self.shell, name)
            for forbidden in ("EEA_Execution", "OrderSend", "risk_fraction"):
                self.assertNotIn(forbidden, body)

    def test_contexts_have_no_account_identifiers(self):  # TC-AI-05
        for name in ("string EEA_AiContextNewsData", "string EEA_AiContextNewsEvent",
                     "string EEA_AiContextDiagnostics", "string EEA_AiContextStatus", "string EEA_AiContextPreBrief"):
            body = section(self.shell, name)
            for forbidden in ("account_fingerprint", "ACCOUNT_LOGIN", "login", "password", "data_root+\"/current"):
                self.assertNotIn(forbidden, body)

    def test_panel_buttons_rate_limited(self):
        panel = read("Runtime/SymbolSelectionPanel.mqh")
        handler = panel.split('sparam==EEA_PANEL_OVERLAY_PREFIX+"Ai_BtnAsk" ||', 1)[1].split("return;\n     }", 1)[0]
        self.assertIn("GetTickCount()-g_panel_state.ai_request_tick<60000", handler)

    def test_panel_ai_view_shows_every_report_slot(self):
        panel = read("Runtime/SymbolSelectionPanel.mqh")
        types = re.search(r"#define EEA_AI_TYPES (\d+)", self.client).group(1)
        self.assertIn("#define EEA_AI_VIEW_SLOTS " + types, panel)
        for decl in ("string ai_title[EEA_AI_VIEW_SLOTS];", "int ai_line_count[EEA_AI_VIEW_SLOTS];",
                     "string ai_lines[EEA_AI_VIEW_SLOTS*8];"):
            self.assertIn(decl, panel)
        dash = section(panel, "void EEA_SymbolPanelDashAi")
        self.assertIn("for(int t=0;t<EEA_AI_VIEW_SLOTS;t++)", dash)
        # tighter pitch so five slots end above the status bar (y 572): 128+104+(15+5*13+4)+4*(15+3*13+4)=548
        self.assertIn("ry+=15;", dash)
        self.assertIn("ry+=13;", dash)
        self.assertIn("ry+=4;", dash)
        publish = section(self.shell, "void EEA_PublishAiView")
        self.assertIn("t<EEA_AI_TYPES && t<EEA_AI_VIEW_SLOTS", publish)
        self.assertNotIn("t<4", publish)
        self.assertIn('"Pre-news brief"', publish)


if __name__ == "__main__":
    unittest.main()
