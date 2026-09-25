#!/usr/bin/env python3
"""Verdict for the M1 MuSHRoom jobs on T2: stage records + reports -> verdict.json, exit code.

    python scripts/mushroom_verdict.py prep  --out /kaggle/working --rooms koivu vr_room
    python scripts/mushroom_verdict.py train --out /kaggle/working --rooms koivu vr_room

prep:  every room was prepared, the device poses survived triangulation unchanged, and each
       dataset has train/val/xseq images. How much the image-only (sfm) reconstruction
       registered is a RESULT, reported, never a failure.
train: every run finished and was evaluated on both test sets at its final step. A run
       that could not be scored (no common test views) counts only when it recorded why.

Like t2_verdict.py, a missing or damaged input fails its own check and never crashes the
verdict. Nothing is thresholded that has not been measured. Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t2_verdict import load_json, load_stages  # noqa: E402

ARMS = ("device", "sfm")
VARIANTS = ("baseline", "indoor")


def run_name(room, arm, variant):
    return f"mushroom_{room}_{arm}_{variant}"


def stage_check(stages, check):
    failed = [s["name"] for s in stages if s.get("required") and s.get("status") != "ok"]
    check("required stages ran", stages and not failed,
          f"failed: {failed}" if failed else f"{len(stages)} stage(s) recorded" if stages
          else "stages.jsonl missing or empty")


def prep(out: Path, rooms) -> dict:
    stages, checks, summary = load_stages(out / "stages.jsonl"), [], {}

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "required": True, "detail": detail})

    stage_check(stages, check)
    for room in rooms:
        rep, err = load_json(out / "rooms" / f"{room}.prep_report.json")
        tar = out / "rooms" / f"mushroom_{room}.tar"
        if err:
            check(f"{room}: prepared", False, err)
            continue
        ds = rep.get("datasets", {})
        dev, sfm = ds.get("device", {}), ds.get("sfm", {})
        check(f"{room}: prepared", tar.is_file(), "tarball present" if tar.is_file() else f"{tar.name} missing")
        moved = dev.get("max_pose_change_after_triangulation")
        check(f"{room}: device poses unchanged by triangulation", moved is not None and moved <= 1e-6,
              f"max change {moved}")
        for arm in ARMS:
            sizes = ds.get(arm, {}).get("split_sizes", {})
            check(f"{room}: {arm} has train/val/xseq images", all(sizes.get(k) for k in ("train", "val", "xseq")),
                  str(sizes))
        summary[room] = {
            "images": rep.get("images"),
            "registered": {arm: ds.get(arm, {}).get("registered") for arm in ARMS},
            "sfm_coverage_long": sfm.get("coverage_long"),
            "sfm_models": sfm.get("models"),
            "sfm_vs_device_pose_agreement": rep.get("sfm_vs_device_pose_agreement"),
            "split_sizes": {arm: ds.get(arm, {}).get("split_sizes") for arm in ARMS},
            "timings_s": rep.get("timings_s"),
        }
    return {"tier": "T2", "job": "m1_mushroom_prep", "passed": all(c["ok"] for c in checks),
            "checks": checks, "stages": stages, "summary": summary}


def final_metrics(stats: dict, prefix: str):
    """{step: {psnr, ssim, lpips, ...}} of one test set's eval files, e.g. val_step14999."""
    out = {}
    for key, v in (stats or {}).items():
        if key.startswith(prefix + "_step") and isinstance(v, dict) and "psnr" in v:
            step = int("".join(c for c in key[len(prefix):] if c.isdigit()) or 0)
            out[step + 1] = {m: v.get(m) for m in ("psnr", "ssim", "lpips", "cc_psnr", "cc_ssim", "num_GS") if m in v}
    return dict(sorted(out.items()))


def train(out: Path, rooms) -> dict:
    stages, checks, summary = load_stages(out / "stages.jsonl"), [], {}

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "required": True, "detail": detail})

    # training runs are best-effort stages (one crash must not cost the others), so only
    # the non-run stages are held to "required" here; each run has its own check below.
    stage_check([s for s in stages if not s.get("name", "").startswith("train ")], check)
    env, err = load_json(out / "verify_env.json")
    check("environment matches pins", env and env.get("passed"), err or ("verify_env passed" if env.get("passed")
          else "failed: " + ", ".join(c["check"] for c in env.get("checks", []) if c.get("required") and not c.get("ok"))))

    for room in rooms:
        for variant in VARIANTS:
            for arm in ARMS:
                name = run_name(room, arm, variant)
                d = out / "work" / name
                skipped, _ = load_json(d / "skipped.json")
                if skipped:
                    check(f"{name}", bool(skipped.get("reason")), f"skipped: {skipped.get('reason')}")
                    summary[name] = {"skipped": skipped.get("reason")}
                    continue
                legs, err = load_json(d / "run.json")
                if err or not isinstance(legs, list) or not legs:
                    check(f"{name}", False, err or "run.json holds no legs")
                    continue
                last = legs[-1]
                val, xseq = final_metrics(last.get("stats"), "val"), final_metrics(last.get("stats"), "xseq")
                final = max(val) if val else None
                ok = last.get("status") == "completed" and final is not None and final in xseq
                check(f"{name}", ok, f"{last.get('status')}, exit {last.get('exit_code')}, "
                      + (f"step {final}: val PSNR {val[final]['psnr']:.2f}, xseq PSNR {xseq[final]['psnr']:.2f}"
                         if ok else f"eval val steps {list(val)}, xseq steps {list(xseq)}"))
                train_stats = [v for k, v in (last.get("stats") or {}).items() if k.startswith("train_step")]
                summary[name] = {
                    "status": last.get("status"), "legs": len(legs),
                    "wall_s_per_leg": [l.get("wall_s") for l in legs],
                    "gpu_used_mib_peak": last.get("gpu_used_mib_peak"),
                    "torch_mem_gb": train_stats[-1].get("mem") if train_stats else None,
                    "val": val, "xseq": xseq,
                }
    prep_summary = {}
    for room in rooms:
        rep, _ = load_json(out / "logs" / "prep" / f"{room}.prep_report.json")
        if rep:
            prep_summary[room] = {"sfm_coverage_long": rep.get("datasets", {}).get("sfm", {}).get("coverage_long"),
                                  "sfm_vs_device_pose_agreement": rep.get("sfm_vs_device_pose_agreement")}
    return {"tier": "T2", "job": "m1_mushroom_train", "passed": all(c["ok"] for c in checks),
            "checks": checks, "stages": stages, "summary": {"runs": summary, "prep": prep_summary}}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("job", choices=["prep", "train"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rooms", nargs="+", required=True)
    a = ap.parse_args()
    v = (prep if a.job == "prep" else train)(a.out, a.rooms)
    tmp = a.out / "verdict.json.tmp"
    tmp.write_text(json.dumps(v, indent=2))
    tmp.replace(a.out / "verdict.json")
    print(f"M1 MuSHRoom {a.job} verdict: {'PASSED' if v['passed'] else 'FAILED'}")
    for c in v["checks"]:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']:<50} {c['detail']}")
    return 0 if v["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
