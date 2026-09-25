#!/usr/bin/env python3
"""M1 T2 gate verdict: stage records + run.json files -> verdict.json and an exit code.

    python scripts/t2_verdict.py --out /kaggle/working

The session's exit code, and so the Kaggle run status, is this verdict. A run is not
"complete" because the notebook ran to the end, and it is not "failed" because an optional
step broke: each gate check is explicit and says why it passed or failed.

Robust by design: a missing or damaged input fails the check that needs it and is recorded
as such. It never crashes the verdict, so the verdict always exists to be fetched.
Thresholds are deliberately absent where none has been measured: the resumed-vs-reference
comparison is reported, not judged (project rule: no fabricated numbers).

Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

BASELINE, RESUME = "m1_drjohnson", "m1_resume_check"
REF_PREFIX = "m1_resume_ref_"


def load_json(path: Path):
    try:
        return json.loads(path.read_text()), None
    except FileNotFoundError:
        return None, f"{path.name} missing"
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable: {type(exc).__name__}: {exc}"


def load_stages(path: Path) -> list:
    stages = []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return stages
    for line in lines:
        try:
            stages.append(json.loads(line))
        except ValueError:
            stages.append({"name": "?", "status": "unparsed", "raw": line})
    return stages


def final_eval(leg: dict):
    """Metrics of the highest-step val_* stats of a run.json leg, or None."""
    vals = {k: v for k, v in (leg.get("stats") or {}).items()
            if k.startswith("val_step") and isinstance(v, dict) and "psnr" in v}
    if not vals:
        return None
    key = max(vals, key=lambda k: int("".join(c for c in k if c.isdigit()) or 0))
    return {"stats": key, **{m: vals[key].get(m) for m in ("psnr", "ssim", "lpips", "num_GS")}}


def summarise_run(work: Path, name: str) -> dict:
    legs, err = load_json(work / name / "run.json")
    if err:
        return {"ok": False, "detail": err}
    if not isinstance(legs, list) or not legs:
        return {"ok": False, "detail": "run.json holds no legs"}
    last = legs[-1]
    ev = final_eval(last)
    out = {"legs": len(legs), "status": last.get("status"), "exit_code": last.get("exit_code"),
           "resumed_from": last.get("resumed_from"), "wall_s_per_leg": [l.get("wall_s") for l in legs],
           "gpu_used_mib_peak": last.get("gpu_used_mib_peak"), "hardware": last.get("hardware"),
           "eval": ev}
    out["ok"] = last.get("status") == "completed" and ev is not None
    out["detail"] = (f"{last.get('status')}, exit {last.get('exit_code')}, "
                     f"PSNR {ev['psnr']:.2f}" if ev and ev.get("psnr") is not None
                     else f"{last.get('status')}, exit {last.get('exit_code')}, no eval stats")
    return out


def verdict(out: Path) -> dict:
    work = out / "work"
    stages = load_stages(out / "stages.jsonl")
    checks = []

    def check(name, ok, detail, required=True):
        checks.append({"check": name, "ok": bool(ok), "required": required, "detail": detail})

    failed = [s["name"] for s in stages if s.get("required") and s.get("status") != "ok"]
    check("required stages ran", stages and not failed,
          f"failed: {failed}" if failed else f"{len(stages)} stage(s) recorded" if stages
          else "stages.jsonl missing or empty")

    env, err = load_json(out / "verify_env.json")
    check("environment matches pins", env and env.get("passed"),
          err or ("verify_env passed" if env.get("passed") else
                  "failed: " + ", ".join(c["check"] for c in env.get("checks", [])
                                         if c.get("required") and not c.get("ok"))))

    base = summarise_run(work, BASELINE)
    check("baseline trained and evaluated", base["ok"], base["detail"])
    hw = base.get("hardware") or {}
    check("hardware recorded (all GPUs + the one used)",
          hw.get("gpus_present") and hw.get("gpu_used"),
          f"{hw.get('gpus_present')} present, used {(hw.get('gpu_used') or {}).get('name')} "
          f"#{(hw.get('gpu_used') or {}).get('index')}" if hw else "no hardware block")

    res = summarise_run(work, RESUME)
    check("killed run resumed and finished", res["ok"] and res.get("resumed_from"),
          res["detail"] + ("" if res.get("resumed_from") else "; final leg did not resume"))

    # What the session was asked for (run_t2.sh writes it first). Older sessions lack it.
    session, _ = load_json(out / "logs" / "session.json")
    session = session if isinstance(session, dict) else {}
    if session.get("continue"):
        restored, err = load_json(out / "logs" / "restore.json")
        runs = (restored or {}).get("runs") or []
        check("previous session restored (--continue)", runs,
              err or (f"{len(runs)} run(s) restored: {', '.join(runs)}" if runs
                      else "continue requested, nothing restored"))

    refs = {p.name: summarise_run(work, p.name) for p in sorted(work.glob(REF_PREFIX + "*"))
            if p.is_dir()}
    ref_psnr = [r["eval"]["psnr"] for r in refs.values() if r["ok"] and r["eval"].get("psnr") is not None]
    need = max(2, int(session.get("resume_refs") or 2))
    check("uninterrupted references for the resume check", len(ref_psnr) >= need,
          f"{len(ref_psnr)} usable of {len(refs)} (need >= {need}: 2 for a noise band, "
          f"or as many as the session asked for)")

    comparison = None
    if ref_psnr and res.get("eval") and res["eval"].get("psnr") is not None:
        p = res["eval"]["psnr"]
        comparison = {"resumed_psnr": p, "reference_psnr": ref_psnr,
                      "reference_spread": round(max(ref_psnr) - min(ref_psnr), 4),
                      "within_reference_range": min(ref_psnr) <= p <= max(ref_psnr),
                      "note": "reported, not judged: no tolerance has been measured yet"}

    passed = all(c["ok"] for c in checks if c["required"])
    return {"tier": "T2", "passed": passed, "checks": checks, "stages": stages,
            "runs": {BASELINE: base, RESUME: res, **refs}, "resume_comparison": comparison}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="session output dir (holds work/)")
    args = ap.parse_args()
    v = verdict(args.out)
    tmp = args.out / "verdict.json.tmp"
    tmp.write_text(json.dumps(v, indent=2))
    tmp.replace(args.out / "verdict.json")
    print(f"M1 T2 verdict: {'PASSED' if v['passed'] else 'FAILED'}")
    for c in v["checks"]:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']:<50} {c['detail']}")
    if v["resume_comparison"]:
        print(f"  info  resume vs references: {v['resume_comparison']}")
    return 0 if v["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
