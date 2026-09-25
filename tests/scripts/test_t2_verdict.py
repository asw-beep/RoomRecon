"""scripts/t2_verdict.py: the gate verdict must be right, and must exist whatever broke."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import t2_verdict  # noqa: E402

HW = {"gpus_present": 2, "gpu_used": {"index": 0, "uuid": "GPU-a", "name": "Tesla T4"}}


def leg(status="completed", psnr=25.0, resumed_from=None, step=2999):
    return {"status": status, "exit_code": 0 if status == "completed" else -9, "wall_s": 100.0,
            "resumed_from": resumed_from, "hardware": HW,
            "stats": {f"val_step{step}": {"psnr": psnr, "ssim": 0.8, "lpips": 0.3, "num_GS": 1}}}


class Verdict(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())
        (self.out / "work").mkdir()

    def write_run(self, name, legs):
        d = self.out / "work" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "run.json").write_text(json.dumps(legs))

    def write_passing_session(self):
        stages = [{"name": n, "required": True, "status": "ok", "exit_code": 0, "wall_s": 1}
                  for n in ("pin gpu", "setup", "verify env", "data", "baseline", "references", "resume check")]
        (self.out / "stages.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stages))
        (self.out / "verify_env.json").write_text(json.dumps({"passed": True, "checks": []}))
        self.write_run("m1_drjohnson", [leg(psnr=29.0, step=14999)])
        self.write_run("m1_resume_ref_1", [leg(psnr=25.2)])
        self.write_run("m1_resume_ref_2", [leg(psnr=25.4)])
        self.write_run("m1_resume_check", [leg(psnr=25.3, resumed_from="/x/resume.pt")])

    def failed(self, v):
        return [c["check"] for c in v["checks"] if not c["ok"]]

    def test_passing_session(self):
        self.write_passing_session()
        v = t2_verdict.verdict(self.out)
        self.assertTrue(v["passed"], self.failed(v))
        self.assertTrue(v["resume_comparison"]["within_reference_range"])

    def test_empty_output_fails_without_crashing(self):
        v = t2_verdict.verdict(self.out)
        self.assertFalse(v["passed"])
        self.assertEqual(len(v["checks"]), 6)

    def test_required_stage_failure_fails_the_gate(self):
        self.write_passing_session()
        with (self.out / "stages.jsonl").open("a") as f:
            f.write(json.dumps({"name": "data", "required": True, "status": "failed"}) + "\n")
        self.assertIn("required stages ran", self.failed(t2_verdict.verdict(self.out)))

    def test_best_effort_stage_failure_does_not(self):
        self.write_passing_session()
        with (self.out / "stages.jsonl").open("a") as f:
            f.write(json.dumps({"name": "restore", "required": False, "status": "failed"}) + "\n")
        self.assertTrue(t2_verdict.verdict(self.out)["passed"])

    def test_resume_check_must_actually_resume(self):
        self.write_passing_session()
        self.write_run("m1_resume_check", [leg(psnr=25.3, resumed_from=None)])
        self.assertIn("killed run resumed and finished", self.failed(t2_verdict.verdict(self.out)))

    def test_killed_last_leg_fails(self):
        self.write_passing_session()
        self.write_run("m1_drjohnson", [leg(status="killed")])
        self.assertIn("baseline trained and evaluated", self.failed(t2_verdict.verdict(self.out)))

    def test_one_reference_is_not_a_noise_band(self):
        self.write_passing_session()
        (self.out / "work/m1_resume_ref_2/run.json").unlink()
        self.assertIn("uninterrupted references for the resume check",
                      self.failed(t2_verdict.verdict(self.out)))

    def write_session(self, **kw):
        (self.out / "logs").mkdir(exist_ok=True)
        (self.out / "logs/session.json").write_text(json.dumps(kw))

    def test_fewer_references_than_asked_fails(self):
        self.write_passing_session()
        self.write_session(resume_refs=4)
        self.write_run("m1_resume_ref_3", [leg(psnr=25.3)])
        self.assertIn("uninterrupted references for the resume check",
                      self.failed(t2_verdict.verdict(self.out)))
        self.write_run("m1_resume_ref_4", [leg(psnr=25.3)])
        self.assertTrue(t2_verdict.verdict(self.out)["passed"])

    def test_continue_must_restore_something(self):
        self.write_passing_session()
        self.write_session(**{"continue": True, "resume_refs": 2})
        self.assertIn("previous session restored (--continue)", self.failed(t2_verdict.verdict(self.out)))
        (self.out / "logs/restore.json").write_text(json.dumps({"restored_from": [], "runs": []}))
        self.assertIn("previous session restored (--continue)", self.failed(t2_verdict.verdict(self.out)))
        (self.out / "logs/restore.json").write_text(
            json.dumps({"restored_from": ["/kaggle/input/x/work"], "runs": ["m1_drjohnson"]}))
        self.assertTrue(t2_verdict.verdict(self.out)["passed"])

    def test_fresh_session_has_no_restore_check(self):
        self.write_passing_session()
        self.write_session(**{"continue": False, "resume_refs": 2})
        v = t2_verdict.verdict(self.out)
        self.assertTrue(v["passed"])
        self.assertNotIn("previous session restored (--continue)", [c["check"] for c in v["checks"]])

    def test_damaged_inputs_fail_their_check_only(self):
        self.write_passing_session()
        (self.out / "verify_env.json").write_text("{")
        (self.out / "work/m1_drjohnson/run.json").write_text("")
        failed = self.failed(t2_verdict.verdict(self.out))
        self.assertIn("environment matches pins", failed)
        self.assertIn("baseline trained and evaluated", failed)
        self.assertNotIn("killed run resumed and finished", failed)

    def test_single_gpu_hardware_is_fine(self):
        self.write_passing_session()
        one = leg(psnr=29.0)
        one["hardware"] = {"gpus_present": 1, "gpu_used": {"index": 0, "uuid": "GPU-a", "name": "RTX 3050"}}
        self.write_run("m1_drjohnson", [one])
        self.assertTrue(t2_verdict.verdict(self.out)["passed"])

    def test_final_eval_picks_highest_step_numerically(self):
        ev = t2_verdict.final_eval({"stats": {"val_step999": {"psnr": 1.0},
                                              "val_step14999": {"psnr": 2.0},
                                              "train_step14999_rank0": {"mem": 3.0}}})
        self.assertEqual((ev["stats"], ev["psnr"]), ("val_step14999", 2.0))

    def test_main_writes_verdict_file_and_exit_code(self):
        self.write_passing_session()
        sys.argv = ["t2_verdict", "--out", str(self.out)]
        self.assertEqual(t2_verdict.main(), 0)
        self.assertTrue(json.loads((self.out / "verdict.json").read_text())["passed"])


if __name__ == "__main__":
    unittest.main()
