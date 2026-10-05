"""G19 EA side of REQ-019: operator mode store, remote command inbox, entry block (source checks)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(text, start):
    return text.split(start, 1)[1].split("\n  }\n", 1)[0]


class ModeStoreTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Integration/RemoteModeRuntime.mqh").read_text(encoding="utf-8")
        self.load = section(self.src, "void EEA_RemoteModeLoad(")

    def test_t1_missing_file_bootstraps_running(self):
        missing = self.load.split("if(!FileIsExist(path,0))", 1)[1].split("return;", 1)[0]
        self.assertIn("s.operator_paused=false; s.state_version=1;", missing)
        self.assertIn('"OPERATOR_MODE_BOOTSTRAP"', missing)

    def test_t2_unreadable_or_foreign_file_fails_closed(self):
        self.assertIn('reason="OPERATOR_MODE_UNREADABLE";', self.load)
        self.assertIn("loaded.account_id!=account_id || loaded.config_version!=config_version", self.load)
        tail = self.load.split("// T2: fail closed", 1)[1]
        self.assertIn("s.initialized=true; s.operator_paused=true;", tail)
        self.assertIn('"OPERATOR_MODE_FAIL_CLOSED"', tail)
        # Defaults start paused until a trusted state is read.
        self.assertIn("EEA_RemoteModeDefaults(s);                       // operator_paused=true", self.load)

    def test_parse_requires_explicit_boolean_and_identity(self):
        parse = section(self.src, "bool EEA_RemoteModeParse(")
        self.assertIn('if(paused!="true" && paused!="false") return false;', parse)
        self.assertIn('if(s.account_id=="" || s.config_version=="" || s.state_version<=0) return false;', parse)


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Integration/RemoteModeRuntime.mqh").read_text(encoding="utf-8")
        self.inbox = section(self.src, "int EEA_RemoteModeProcessInbox(")

    def test_commit_then_apply(self):
        self.assertIn("EEA_EvaluateRemoteModeCommand(s,c,evidence,TimeGMT(),next,d);", self.inbox)
        self.assertIn('if(EEA_RemoteModeSave(next,root,d.reason_code)) { s=next; applied=true; }', self.inbox)
        self.assertIn('else d.reason_code="REMOTE_STATE_COMMIT_FAILED";', self.inbox)

    def test_one_result_per_command_and_file_removed(self):
        for field in ("command_id", "accepted", "applied", "state_before", "state_after", "reason_codes",
                      "ea_state_version", "observed_at_utc"):
            self.assertIn(f'\\"{field}\\":', self.inbox)
        self.assertIn('EEA_WriteAtomicText(EEA_RemoteResultDir(root)+"/"+c.command_id+".json",result);', self.inbox)
        self.assertIn("FileDelete(path,0);", self.inbox)
        self.assertIn("ArraySort(files);", self.inbox)

    def test_command_ids_cannot_escape_the_results_folder(self):
        safe = section(self.src, "bool EEA_RemoteSafeId(")
        self.assertIn("if(len<8 || len>64) return false;", safe)
        self.assertIn("ch=='-' || ch=='_'", safe)
        self.assertIn("return EEA_RemoteSafeId(c.command_id);", self.src)

        def mirror(s):
            return 8 <= len(s) <= 64 and re.fullmatch(r"[A-Za-z0-9_\-]+", s) is not None
        self.assertTrue(mirror("tg-000001-ab12cd34"))
        for bad in ("../../x-evil", "tg/000001", "short", "a" * 65, "tg-0001 ab"):
            self.assertFalse(mirror(bad), bad)

    def test_attestation_flags_must_be_literal_true(self):
        parse = section(self.src, "bool EEA_RemoteCommandParse(")
        for flag in ("private_chat_attested", "sender_authenticated", "source_authenticated"):
            self.assertIn(f'c.{flag}=(EEA_RiskLedgerField(json,"{flag}")=="true");', parse)


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.shell = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")

    def test_paused_blocks_entries_but_not_management(self):
        block = self.shell.split("EEA_RemoteModeTimer();\n", 1)[1].split("EEA_CandidateLedgerUpdate(", 1)[0]
        self.assertIn('if(EEA_RemoteEntriesPaused())\n                g_live_runtime.last_reason="OPERATOR_PAUSED_ENTRIES";', block)
        self.assertIn("EEA_ControlledLiveOnTimer(", block.split("else", 1)[1])
        self.assertIn("bool EEA_RemoteEntriesPaused() { return !g_remote_loaded || g_remote_mode.operator_paused; }",
                      self.shell)

    def test_seven_resume_evidence_facts(self):
        ev = section(self.shell, "void EEA_RemoteResumeEvidenceNow(")
        for token in ('g_runtime.status.runtime_state=="OBSERVING"', "!g_live_runtime.recovery_blocked",
                      '=="UNKNOWN"', "TERMINAL_CONNECTED", "TERMINAL_TRADE_ALLOWED", "MQL_TRADE_ALLOWED",
                      "g_trade_manager.loaded", "<=120"):
            self.assertIn(token, ev)

    def test_mode_reloaded_when_account_changes(self):
        timer = section(self.shell, "void EEA_RemoteModeTimer(")
        self.assertIn("g_remote_mode.account_id!=g_runtime.account.account_fingerprint", timer)
        self.assertIn("EEA_RemoteModeProcessInbox(", timer)

    def test_overview_shows_operator_pause(self):
        panel = (ROOT / "Runtime/SymbolSelectionPanel.mqh").read_text(encoding="utf-8")
        self.assertIn('"PAUSED by operator (Telegram)"', panel)


if __name__ == "__main__":
    unittest.main()
