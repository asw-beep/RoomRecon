"""scripts/train.py helpers: leg status, stats collection, and the run.json history."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import train  # noqa: E402


class LegStatus(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(train.leg_status(0), "completed")
        self.assertEqual(train.leg_status(1), "failed")
        self.assertEqual(train.leg_status(-9), "killed")   # SIGKILL, subprocess convention


class RunLog(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.log = self.dir / "run.json"

    def test_history_appends_one_leg_each(self):
        train.append_leg(self.log, {"status": "killed"})
        train.append_leg(self.log, {"status": "completed"})
        self.assertEqual([l["status"] for l in json.loads(self.log.read_text())], ["killed", "completed"])
        self.assertFalse(self.log.with_suffix(".tmp").exists())

    def test_corrupt_history_is_kept_aside_not_fatal(self):
        self.log.write_text("{truncated")
        train.append_leg(self.log, {"status": "completed"})
        self.assertEqual(len(json.loads(self.log.read_text())), 1)
        self.assertEqual(self.log.with_suffix(".corrupt.json").read_text(), "{truncated")

    def test_last_leg_completed(self):
        self.assertFalse(train.last_leg_completed(self.log))           # no file
        train.append_leg(self.log, {"status": "killed"})
        self.assertFalse(train.last_leg_completed(self.log))
        train.append_leg(self.log, {"status": "completed"})
        self.assertTrue(train.last_leg_completed(self.log))

    def test_pre_status_records_do_not_count_as_completed(self):
        self.log.write_text(json.dumps([{"exit_code": 0}]))   # written before `status` existed
        self.assertFalse(train.last_leg_completed(self.log))


class ReadStats(unittest.TestCase):
    def test_damaged_file_recorded_not_fatal(self):
        d = Path(tempfile.mkdtemp())
        (d / "stats").mkdir()
        (d / "stats/val_step2999.json").write_text(json.dumps({"psnr": 25.3}))
        (d / "stats/train_step2999_rank0.json").write_text("")
        s = train.read_stats(d)
        self.assertEqual(s["val_step2999"], {"psnr": 25.3})
        self.assertIn("error", s["train_step2999_rank0"])

    def test_no_stats_dir(self):
        self.assertEqual(train.read_stats(Path(tempfile.mkdtemp())), {})


if __name__ == "__main__":
    unittest.main()
