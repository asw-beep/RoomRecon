#!/usr/bin/env python3
"""Headless 3DGS training, identical on every tier (ADR-005 constraint 3).

    python scripts/train.py --config configs/m1_drjohnson.yaml

Wraps gsplat's example trainer (v1.5.3 + scripts/patches/gsplat-1.5.3-resume.patch).
Re-running the same command after a kill or pre-emption continues from the last
resume.pt instead of starting over (ADR-005 constraint 2).

Paths in the config may use ${ROOMRECON_DATA} and ${ROOMRECON_WORK}, which default to
~/roomrecon/datasets and ~/roomrecon/work. Every run writes <result_dir>/run.json with
tier, pipeline version, resolved config, wall time and peak VRAM.

The job is pinned to exactly one GPU (scripts/gpu.py): on a multi-GPU machine the
trainer, the VRAM sampler and the hardware record all refer to the same device.
"""
import argparse
import datetime
import hashlib
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
import gpu  # noqa: E402
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
    """Used memory of the pinned GPU via nvidia-smi, so the desktop baseline is visible too.

    Polling misses short spikes; the trainer's own torch peak (stats/train_*.json "mem")
    is the primary number, this one shows what the whole device went through.
    """

    def __init__(self, uuid: str, every: float = 2.0):
        super().__init__(daemon=True)
        self.uuid, self.every, self.samples, self.stop = uuid, every, [], threading.Event()

    def run(self):
        while not self.stop.is_set():
            used = gpu.memory_used_mib(self.uuid)
            if used is not None:
                self.samples.append(used)
            self.stop.wait(self.every)


def leg_status(rc: int) -> str:
    """Negative return codes are signals (subprocess convention): the leg was killed."""
    return "completed" if rc == 0 else ("killed" if rc < 0 else "failed")


def read_stats(result_dir: Path) -> dict:
    """gsplat's own structured stats (val_*: metrics, train_*: torch peak mem, num_GS).

    A file that does not parse is recorded as an error, never fatal: the leg's outcome
    must reach run.json even when one stats file is damaged.
    """
    stats = {}
    for p in sorted(result_dir.glob("stats/*.json")):
        try:
            stats[p.stem] = json.loads(p.read_text())
        except (OSError, ValueError) as exc:
            stats[p.stem] = {"error": f"{type(exc).__name__}: {exc}"}
    return stats


def last_leg_completed(log: Path) -> bool:
    try:
        legs = json.loads(log.read_text())
    except (OSError, ValueError):
        return False
    return bool(legs) and legs[-1].get("status") == "completed"


def append_leg(log: Path, run: dict) -> None:
    """One record per leg, written atomically so a kill mid-write cannot lose the history."""
    history = []
    if log.exists():
        try:
            history = json.loads(log.read_text())
        except ValueError:
            log.replace(log.with_suffix(".corrupt.json"))   # keep it for inspection
    tmp = log.with_suffix(".tmp")
    tmp.write_text(json.dumps(history + [run], indent=2))
    os.replace(tmp, log)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--fresh", action="store_true", help="ignore an existing resume.pt")
    ap.add_argument("--result-dir", help="override the config's result_dir (repeat runs of one config)")
    cli = ap.parse_args()

    cfg = yaml.safe_load(cli.config.read_text())
    data_dir = resolve(cfg["data_dir"])
    result_dir = Path(resolve(cli.result_dir or cfg["result_dir"]))
    if not Path(data_dir, "sparse").is_dir():
        sys.exit(f"{data_dir} has no sparse/ - expected a COLMAP-format scene")
    trainer = TOOLCHAIN / "gsplat/examples/simple_trainer.py"
    if "_save_resume" not in trainer.read_text():
        sys.exit(f"{trainer} lacks the resume patch - run scripts/verify_env.py")

    gpus = gpu.inventory()
    used = gpu.select(gpus)
    if used is None:
        sys.exit(f"no usable GPU: found {len(gpus)}, CUDA_VISIBLE_DEVICES="
                 f"{os.environ.get('CUDA_VISIBLE_DEVICES')!r}")
    # Pin explicitly so the trainer cannot land on a different device than the one measured.
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": used["uuid"]}
    # Optional explicit train/test split (JSON: split name -> image names), read by the
    # gsplat split patch. Without it gsplat holds out every Nth image.
    env.pop("ROOMRECON_SPLIT", None)
    split_file = None
    if cfg.get("split"):
        split_file = Path(resolve(cfg["split"]))
        if not split_file.is_file():
            sys.exit(f"split file {split_file} not found")
        if "ROOMRECON_SPLIT" not in (trainer.parent / "datasets/colmap.py").read_text():
            sys.exit(f"{trainer.parent} lacks the split patch - run scripts/verify_env.py")
        env["ROOMRECON_SPLIT"] = str(split_file)

    result_dir.mkdir(parents=True, exist_ok=True)
    log = result_dir / "run.json"
    # Idempotent: a finished run is not retrained. Re-running a whole session after a
    # pre-emption therefore skips what finished and resumes what did not.
    if not cli.fresh and last_leg_completed(log):
        print(f"[train] {result_dir} already completed, skipping (--fresh to retrain)", flush=True)
        return 0
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
        "config_hash": "sha256:" + hashlib.sha256(cli.config.read_bytes()).hexdigest(),
        "hardware": gpu.describe(gpus, used),
        "resolved": {**cfg, "data_dir": data_dir, "result_dir": str(result_dir)},
        "split": ({"file": str(split_file),
                   "sha256": hashlib.sha256(split_file.read_bytes()).hexdigest()} if split_file else None),
        "command": cmd,
        "resumed_from": str(resume_pt) if resuming else None,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    print(f"[train] tier {run['tier']}  version {run['pipeline_version']}"
          f"  GPU {used['index']} ({used['name']}) of {len(gpus)}"
          f"  {'RESUMING' if resuming else 'fresh start'}", flush=True)

    sampler = VramSampler(used["uuid"])
    sampler.start()
    t0 = time.time()
    # simple_trainer imports its siblings (datasets/, utils) relative to examples/.
    rc = subprocess.run(cmd, cwd=trainer.parent, env=env).returncode
    sampler.stop.set()

    run.update({
        "status": leg_status(rc),
        "exit_code": rc,
        "wall_s": round(time.time() - t0, 1),
        "gpu_used_mib_peak": max(sampler.samples, default=None),
        "gpu_used_mib_min": min(sampler.samples, default=None),
        "stats": read_stats(result_dir),
    })
    append_leg(log, run)
    print(f"[train] {run['status']} (exit {rc}), {run['wall_s']}s, peak GPU "
          f"{run['gpu_used_mib_peak']} MiB (incl. baseline {run['gpu_used_mib_min']}) -> {log}",
          flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
