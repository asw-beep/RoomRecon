#!/usr/bin/env python3
"""Headless 3DGS training, identical on every tier (ADR-005 constraint 3).

    python scripts/train.py --config configs/m1_drjohnson.yaml

Wraps gsplat's example trainer (v1.5.3 + scripts/patches/gsplat-1.5.3-resume.patch).
Re-running the same command after a kill or pre-emption continues from the last
resume.pt instead of starting over (ADR-005 constraint 2).

Paths in the config may use ${ROOMRECON_DATA} and ${ROOMRECON_WORK}, which default to
~/roomrecon/datasets and ~/roomrecon/work. Every run writes <result_dir>/run.json with
tier, pipeline version, resolved config, wall time and peak VRAM.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from verify_env import TOOLCHAIN, detect_tier  # noqa: E402

# Owned by this launcher; a config that sets them is rejected.
RESERVED = {"data_dir", "result_dir", "resume", "disable_viewer"}


def resolve(value: str) -> str:
    os.environ.setdefault("ROOMRECON_DATA", str(Path("~/roomrecon/datasets").expanduser()))
    os.environ.setdefault("ROOMRECON_WORK", str(Path("~/roomrecon/work").expanduser()))
    out = os.path.expandvars(os.path.expanduser(value))
    if "$" in out:
        sys.exit(f"unresolved variable in config path: {value}")
    return out


def trainer_args(args: dict) -> list:
    """Config mapping -> tyro CLI flags for simple_trainer.py."""
    flags = []
    for key, val in args.items():
        if key in RESERVED:
            sys.exit(f"trainer_args.{key} is set by train.py, remove it from the config")
        if val is True:
            flags.append(f"--{key}")
        elif val is False or val is None:
            sys.exit(f"trainer_args.{key}: only true flags are supported, omit it instead")
        elif isinstance(val, list):
            flags += [f"--{key}"] + [str(v) for v in val]
        else:
            flags += [f"--{key}", str(val)]
    return flags


def pipeline_version() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


class VramSampler(threading.Thread):
    """Whole-GPU used memory via nvidia-smi, so the desktop baseline is visible too."""

    def __init__(self, every: float = 2.0):
        super().__init__(daemon=True)
        self.every, self.samples, self.stop = every, [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                  "--format=csv,noheader,nounits"], capture_output=True, text=True)
            if out.returncode == 0 and out.stdout.strip():
                self.samples.append(int(out.stdout.split()[0]))
            self.stop.wait(self.every)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--fresh", action="store_true", help="ignore an existing resume.pt")
    cli = ap.parse_args()

    cfg = yaml.safe_load(cli.config.read_text())
    data_dir, result_dir = resolve(cfg["data_dir"]), Path(resolve(cfg["result_dir"]))
    if not Path(data_dir, "sparse").is_dir():
        sys.exit(f"{data_dir} has no sparse/ - expected a COLMAP-format scene")
    trainer = TOOLCHAIN / "gsplat/examples/simple_trainer.py"
    if "_save_resume" not in trainer.read_text():
        sys.exit(f"{trainer} lacks the resume patch - run scripts/verify_env.py")

    result_dir.mkdir(parents=True, exist_ok=True)
    resume_pt = result_dir / "ckpts/resume.pt"
    resuming = resume_pt.exists() and not cli.fresh

    cmd = [sys.executable, str(trainer), cfg.get("strategy", "mcmc"),
           "--data_dir", data_dir, "--result_dir", str(result_dir), "--disable_viewer"]
    cmd += trainer_args(cfg.get("trainer_args", {}))
    if resuming:
        cmd += ["--resume", str(resume_pt)]

    run = {
        "tier": detect_tier(),
        "pipeline_version": pipeline_version(),
        "config": str(cli.config),
        "resolved": {"data_dir": data_dir, "result_dir": str(result_dir), **cfg},
        "command": cmd,
        "resumed_from": str(resume_pt) if resuming else None,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    print(f"[train] tier {run['tier']}  version {run['pipeline_version']}"
          f"  {'RESUMING' if resuming else 'fresh start'}", flush=True)

    sampler = VramSampler()
    sampler.start()
    t0 = time.time()
    # simple_trainer imports its siblings (datasets/, utils) relative to examples/.
    rc = subprocess.run(cmd, cwd=trainer.parent).returncode
    sampler.stop.set()

    run.update({
        "exit_code": rc,
        "wall_s": round(time.time() - t0, 1),
        "gpu_used_mib_peak": max(sampler.samples, default=None),
        "gpu_used_mib_min": min(sampler.samples, default=None),
        "eval": {p.name: json.loads(p.read_text()) for p in sorted(result_dir.glob("stats/val_*.json"))},
    })
    # One record per leg, so a resumed run keeps the history of the interrupted one.
    log = result_dir / "run.json"
    history = json.loads(log.read_text()) if log.exists() else []
    log.write_text(json.dumps(history + [run], indent=2))
    print(f"[train] exit {rc}, {run['wall_s']}s, peak GPU {run['gpu_used_mib_peak']} MiB "
          f"(incl. baseline {run['gpu_used_mib_min']}) -> {log}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
