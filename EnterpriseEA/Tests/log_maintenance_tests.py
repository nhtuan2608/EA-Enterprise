"""NFR-07 audit log rotation (G15) and news state freshness on disk (G16)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AuditRotationTests(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "Storage/AuditLog.mqh").read_text(encoding="utf-8")

    def test_bounded_size_and_retention(self):
        self.assertIn("#define EEA_AUDIT_ROTATE_BYTES 20971520", self.src)
        self.assertIn("#define EEA_AUDIT_KEEP_ARCHIVES 10", self.src)

    def test_rotation_runs_before_every_append(self):
        append = self.src.split("bool Append(EEAEvent &event,const string source)", 1)[1]
        self.assertLess(append.index("RotateIfFull(count);"), append.index("FileWriteArray(m_handle"))
        self.assertIn("if(!IsOpen()) return false;", append)

    def test_archive_name_sorts_by_utc_time(self):
        self.assertIn('Dir()+Stem()+"-"+Stamp(TimeGMT())+".jsonl"', self.src)
        self.assertIn('"%04d%02d%02d-%02d%02d%02d"', self.src)
        self.assertIn('FileFindFirst(Dir()+Stem()+"-*.jsonl"', self.src)
        self.assertIn("ArraySort(names);", self.src)

    def test_failed_move_keeps_writing_and_never_prunes(self):
        rotate = self.src.split("void RotateIfFull(const int incoming)", 1)[1].split("public:", 1)[0]
        self.assertIn("!FileIsExist(archive,0) && FileMove(m_path,0,archive,0)", rotate)
        self.assertIn("if(moved) PruneArchives();", rotate)
        # The live file is reopened whether or not the move succeeded.
        self.assertIn("m_handle=FileOpen(m_path,FILE_READ|FILE_WRITE|FILE_BIN|FILE_SHARE_READ);", rotate)

    def test_news_reaction_dataset_is_not_rotated(self):
        recorder = (ROOT / "News/NewsReactionRecorder.mqh").read_text(encoding="utf-8")
        self.assertNotIn("RotateIfFull", recorder)


class NewsStateFreshnessTests(unittest.TestCase):
    def test_successful_refresh_rewrites_state(self):
        src = (ROOT / "News/NewsCalendar.mqh").read_text(encoding="utf-8")
        update = src.split("void EEA_NewsUpdate(", 1)[1].split("string EEA_NewsStateFor(", 1)[0]
        self.assertIn("if(ok) changed=true;", update)
        self.assertIn("if(changed) EEA_NewsWriteState(rt,root);", update)


if __name__ == "__main__":
    unittest.main()
