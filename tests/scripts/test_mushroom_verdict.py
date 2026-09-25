"""scripts/mushroom_verdict.py: both jobs' verdicts, and that they exist whatever broke."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import mushroom_verdict as mv  # noqa: E402

ROOMS = ["koivu", "vr_room"]


def write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def stages(*names, failed=()):
    return "".join(json.dumps({"name": n, "required": not n.startswith("train "),
                               "status": "failed" if n in failed else "ok"}) + "\n" for n in names)


def prep_report(moved=0.0, sfm_sizes=None):
    sizes = {"train": 10, "val": 2, "xseq": 3}
    return {"images": {"long": 12, "short": 3},
            "datasets": {"device": {"split_sizes": sizes, "registered": {"long": 12, "short": 3},
                                    "max_pose_change_after_triangulation": moved},
                         "sfm": {"split_sizes": sfm_sizes or sizes, "registered": {"long": 9, "short": 3},
                                 "coverage_long": 0.75, "models": [12]}},
            "sfm_vs_device_pose_agreement": {"median_m": 0.01}}


def run_leg(status="completed", val=25.0, xseq=21.0, steps=(2999, 6999, 14999)):
    stats = {}
    for s in steps:
        stats[f"val_step{s}"] = {"psnr": val, "ssim": 0.8, "lpips": 0.2, "num_GS": 1}
        stats[f"xseq_step{s}"] = {"psnr": xseq, "ssim": 0.7, "lpips": 0.3, "num_GS": 1}
    stats["train_step14999_rank0"] = {"mem": 1.5}
    return {"status": status, "exit_code": 0 if status == "completed" else 1, "wall_s": 100.0, "stats": stats}


class Prep(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def passing(self):
        (self.out / "stages.jsonl").write_text(stages("tools", "fetch", "prepare koivu", "prepare vr_room"))
        for r in ROOMS:
            write(self.out / "rooms" / f"{r}.prep_report.json", prep_report())
            (self.out / "rooms" / f"mushroom_{r}.tar").write_bytes(b"x")

    def failed(self, v):
        return [c["check"] for c in v["checks"] if not c["ok"]]

    def test_passing(self):
        self.passing()
        v = mv.prep(self.out, ROOMS)
        self.assertTrue(v["passed"], self.failed(v))
        self.assertEqual(v["summary"]["koivu"]["sfm_coverage_long"], 0.75)

    def test_empty_output_fails_without_crashing(self):
        self.assertFalse(mv.prep(self.out, ROOMS)["passed"])

    def test_moved_device_poses_fail(self):
        self.passing()
        write(self.out / "rooms/koivu.prep_report.json", prep_report(moved=1e-3))
        self.assertIn("koivu: device poses unchanged by triangulation", self.failed(mv.prep(self.out, ROOMS)))

    def test_empty_test_set_fails(self):
        self.passing()
        write(self.out / "rooms/vr_room.prep_report.json", prep_report(sfm_sizes={"train": 5, "val": 0, "xseq": 0}))
        self.assertIn("vr_room: sfm has train/val/xseq images", self.failed(mv.prep(self.out, ROOMS)))


class Train(unittest.TestCase):
    def setUp(self):
        self.out = Path(tempfile.mkdtemp())

    def passing(self):
        names = ["pin gpu", "setup", "verify env", "data"] + [
            f"train {r} {a} {v}" for v in mv.VARIANTS for r in ROOMS for a in mv.ARMS]
        (self.out / "stages.jsonl").write_text(stages(*names))
        write(self.out / "verify_env.json", {"passed": True, "checks": []})
        for r in ROOMS:
            for a in mv.ARMS:
                for v in mv.VARIANTS:
                    write(self.out / "work" / mv.run_name(r, a, v) / "run.json", [run_leg()])

    def failed(self, v):
        return [c["check"] for c in v["checks"] if not c["ok"]]

    def test_passing_reports_every_run_and_step(self):
        self.passing()
        v = mv.train(self.out, ROOMS)
        self.assertTrue(v["passed"], self.failed(v))
        runs = v["summary"]["runs"]
        self.assertEqual(len(runs), 8)
        self.assertEqual(list(runs["mushroom_koivu_device_baseline"]["val"]), [3000, 7000, 15000])

    def test_a_crashed_run_fails_only_itself(self):
        self.passing()
        write(self.out / "work/mushroom_koivu_sfm_indoor/run.json", [run_leg(status="failed")])
        self.assertEqual(self.failed(mv.train(self.out, ROOMS)), ["mushroom_koivu_sfm_indoor"])

    def test_missing_cross_sequence_eval_fails(self):
        self.passing()
        leg = run_leg()
        leg["stats"] = {k: v for k, v in leg["stats"].items() if not k.startswith("xseq")}
        write(self.out / "work/mushroom_vr_room_device_baseline/run.json", [leg])
        self.assertEqual(self.failed(mv.train(self.out, ROOMS)), ["mushroom_vr_room_device_baseline"])

    def test_skip_counts_only_with_a_reason(self):
        self.passing()
        d = self.out / "work/mushroom_koivu_sfm_baseline"
        (d / "run.json").unlink()
        write(d / "skipped.json", {"reason": "no test view registered by both pose sources"})
        self.assertTrue(mv.train(self.out, ROOMS)["passed"])
        write(d / "skipped.json", {"reason": ""})
        self.assertEqual(self.failed(mv.train(self.out, ROOMS)), ["mushroom_koivu_sfm_baseline"])

    def test_failed_setup_fails_the_gate(self):
        self.passing()
        with (self.out / "stages.jsonl").open("a") as f:
            f.write(json.dumps({"name": "data", "required": True, "status": "failed"}) + "\n")
        self.assertIn("required stages ran", self.failed(mv.train(self.out, ROOMS)))

    def test_failed_run_stage_is_judged_by_its_run_not_the_stage_check(self):
        self.passing()
        with (self.out / "stages.jsonl").open("a") as f:
            f.write(json.dumps({"name": "train koivu device baseline", "required": False, "status": "failed"}) + "\n")
        self.assertTrue(mv.train(self.out, ROOMS)["passed"])

    def test_empty_output_fails_without_crashing(self):
        v = mv.train(self.out, ROOMS)
        self.assertFalse(v["passed"])


if __name__ == "__main__":
    unittest.main()
