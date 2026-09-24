#!/usr/bin/env python3
"""Checks the reconstruction environment and says which compute tier it is on.

One command, identical on every tier (ADR-005, Risk #4 environment drift):

    python scripts/verify_env.py            # table, exit 1 if anything required fails
    python scripts/verify_env.py --json     # machine-readable, for job logs

Standard library only, so it runs before anything is installed and reports what is
missing rather than crashing on the first import.

Pins are the versions measured on T1 during M1 (docs/m1-downloads.csv). A different
version on another tier is reported as a failure, not a warning: silent drift between
tiers is exactly the risk this script exists to catch.
"""
import argparse
import importlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

PINS = {
    "python": "3.10",
    "torch": "2.5.1+cu121",
    "cuda": "12.1",
    "gsplat": "1.5.3",
    "numpy": "1.26.4",  # gsplat examples require numpy<2
}

TOOLCHAIN = Path(os.environ.get("ROOMRECON_TOOLCHAIN", "~/roomrecon/toolchain")).expanduser()


def detect_tier() -> str:
    if os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or Path("/kaggle").is_dir():
        return "T2"
    try:
        if "microsoft" in Path("/proc/version").read_text().lower():
            return "T1"
    except OSError:
        pass
    return "T3" if platform.system() == "Linux" else "unknown"


def run(cmd: list) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return (out.stdout + out.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def module_version(name: str):
    try:
        mod = importlib.import_module(name)
    except Exception as exc:  # broken installs raise more than ImportError
        return None, f"import failed: {type(exc).__name__}: {exc}"
    return getattr(mod, "__version__", "unknown"), None


def check_python():
    have = f"{sys.version_info.major}.{sys.version_info.minor}"
    return have == PINS["python"], f"{platform.python_version()} (pin {PINS['python']})"


def check_pinned(name: str):
    def check():
        ver, err = module_version(name)
        if err:
            return False, err
        return ver == PINS[name], f"{ver} (pin {PINS[name]})"
    return check


def check_import(name: str):
    def check():
        ver, err = module_version(name)
        return (False, err) if err else (True, ver)
    return check


def check_gpu():
    try:
        import torch
    except Exception as exc:
        return False, f"torch unavailable: {exc}"
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() is False"
    props = torch.cuda.get_device_properties(0)
    free, total = torch.cuda.mem_get_info(0)
    return True, (
        f"{props.name}, {total / 2**30:.1f} GiB total, {free / 2**30:.1f} GiB free, "
        f"sm_{props.major}{props.minor}"
    )


def check_nvcc():
    nvcc = shutil.which("nvcc") or (
        "/usr/local/cuda-12.1/bin/nvcc" if Path("/usr/local/cuda-12.1/bin/nvcc").exists() else None
    )
    if not nvcc:
        return False, "nvcc not found; CUDA extensions (gsplat kernels) cannot compile"
    m = re.search(r"release (\d+\.\d+)", run([nvcc, "--version"]))
    ver = m.group(1) if m else "unparsed"
    return ver == PINS["cuda"], f"{ver} at {nvcc} (pin {PINS['cuda']}, must match torch)"


def check_binary(name: str, version_args: list):
    def check():
        path = shutil.which(name)
        if not path:
            return False, "not on PATH"
        first = run([path] + version_args).splitlines()
        return True, f"{path}  {first[0][:60] if first else ''}"
    return check


def check_resume_patch():
    trainer = TOOLCHAIN / "gsplat/examples/simple_trainer.py"
    if not trainer.exists():
        return False, f"{trainer} not found"
    ok = "_save_resume" in trainer.read_text()
    return ok, "applied" if ok else "missing: git apply scripts/patches/gsplat-1.5.3-resume.patch"


def check_orbslam():
    lib = TOOLCHAIN / "ORB_SLAM3/lib/libORB_SLAM3.so"
    exe = TOOLCHAIN / "ORB_SLAM3/Examples/Monocular/mono_tum"
    missing = [str(p) for p in (lib, exe) if not p.exists()]
    return not missing, "built" if not missing else f"missing {', '.join(missing)}"


def check_disk():
    free = shutil.disk_usage(Path.home()).free / 2**30
    return free >= 10, f"{free:.0f} GiB free in {Path.home()} (need >= 10)"


# (name, check, tiers where it is required). Checks outside their tiers still run
# and are reported, but cannot fail the gate.
CHECKS = [
    ("python", check_python, {"T1", "T2"}),
    ("torch", check_pinned("torch"), {"T1", "T2"}),
    ("gpu", check_gpu, {"T1", "T2"}),
    ("nvcc", check_nvcc, {"T1", "T2"}),
    ("ninja", check_binary("ninja", ["--version"]), {"T1", "T2"}),
    ("numpy", check_pinned("numpy"), {"T1", "T2"}),
    ("gsplat", check_pinned("gsplat"), {"T1", "T2"}),
    ("gsplat resume patch", check_resume_patch, {"T1", "T2"}),
    ("fused_ssim", check_import("fused_ssim"), {"T1", "T2"}),
    ("torchmetrics", check_import("torchmetrics"), {"T1", "T2"}),
    ("disk", check_disk, {"T1", "T2"}),
    ("ffmpeg", check_binary("ffmpeg", ["-version"]), {"T1"}),
    ("colmap", check_binary("colmap", ["help"]), {"T1"}),
    ("ORB-SLAM3", check_orbslam, {"T1"}),  # T1-only by ADR-005 constraint 1
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args()

    tier = detect_tier()
    rows = []
    for name, check, required_on in CHECKS:
        try:
            ok, detail = check()
        except Exception as exc:
            ok, detail = False, f"check crashed: {type(exc).__name__}: {exc}"
        rows.append({"check": name, "ok": ok, "required": tier in required_on, "detail": detail})
    passed = all(r["ok"] for r in rows if r["required"])

    if args.json:
        print(json.dumps({"tier": tier, "passed": passed, "checks": rows}, indent=2))
    else:
        print(f"RoomRecon environment check  -  tier {tier}  ({platform.node()})\n")
        for r in rows:
            status = "PASS" if r["ok"] else ("FAIL" if r["required"] else "n/a ")
            print(f"  {status}  {r['check']:<20} {r['detail']}")
        print(f"\n{'PASSED' if passed else 'FAILED'}: required checks for tier {tier}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
