#!/usr/bin/env python3
"""GPU inventory and pinning, shared by every script that touches a GPU.

    python scripts/gpu.py            # inventory as JSON
    python scripts/gpu.py --pin      # UUID of the GPU this job should use (for CUDA_VISIBLE_DEVICES)

A machine may have more than one GPU: Kaggle's "T4" accelerator is T4 x2. nvidia-smi
prints one line per GPU, so any code that reads its output as a single value is wrong on
those machines. Everything GPU-related goes through this module instead: list all GPUs,
pin the job to exactly one, and measure only that one.

Pin by UUID, never by index: nvidia-smi numbers GPUs in PCI bus order but CUDA's default
order is fastest-first, so the same index can name different devices to the two.

Standard library only: verify_env.py imports it before anything is installed.
"""
import argparse
import json
import os
import subprocess
import sys

FIELDS = ("index", "uuid", "name", "memory.total", "memory.used", "compute_cap", "driver_version")


def parse_inventory(text: str) -> list:
    """nvidia-smi --query-gpu=<FIELDS> --format=csv,noheader,nounits -> one dict per GPU.

    Raises ValueError on output that does not have the expected shape, rather than
    guessing: a wrong GPU record in run.json is worse than none.
    """
    gpus = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(FIELDS):
            raise ValueError(f"expected {len(FIELDS)} fields, got {len(parts)}: {line!r}")
        idx, uuid, name, total, used, cap, driver = parts
        gpus.append({"index": int(idx), "uuid": uuid, "name": name, "vram_total_mib": int(total),
                     "vram_used_mib": int(used), "compute_cap": cap, "driver": driver})
    return gpus


def inventory() -> list:
    """Every GPU on the machine; [] when there is no NVIDIA driver."""
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={','.join(FIELDS)}",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_inventory(out.stdout) if out.returncode == 0 else []


def select(gpus: list, visible: str = None) -> dict:
    """The GPU a job runs on: the first entry of CUDA_VISIBLE_DEVICES if set, else index 0.

    CUDA_VISIBLE_DEVICES may hold indices or UUIDs. Returns None when nothing matches, so
    the caller fails loudly instead of measuring the wrong device.
    """
    if not gpus:
        return None
    visible = os.environ.get("CUDA_VISIBLE_DEVICES") if visible is None else visible
    if not visible:
        return gpus[0]
    first = visible.split(",")[0].strip()
    for g in gpus:
        if first == str(g["index"]) or first == g["uuid"] or g["uuid"].startswith(first):
            return g
    return None


def memory_used_mib(uuid: str):
    """Used memory of one GPU, by UUID; None if the query fails."""
    try:
        out = subprocess.run(["nvidia-smi", f"--id={uuid}", "--query-gpu=memory.used",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        return int(out.stdout.strip()) if out.returncode == 0 else None
    except ValueError:
        return None


def describe(gpus: list, used: dict) -> dict:
    """Hardware record for run.json: what the machine has and what the job used."""
    return {"gpus_present": len(gpus),
            "gpus": [{k: g[k] for k in ("index", "uuid", "name", "vram_total_mib", "compute_cap")}
                     for g in gpus],
            "gpu_used": None if used is None else {k: used[k] for k in ("index", "uuid", "name")},
            "driver": gpus[0]["driver"] if gpus else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pin", action="store_true", help="print the UUID to pin the job to")
    args = ap.parse_args()
    gpus = inventory()
    if args.pin:
        g = select(gpus)
        if g is None:
            print("no usable GPU (none found, or CUDA_VISIBLE_DEVICES matches none)", file=sys.stderr)
            return 1
        print(g["uuid"])
        return 0
    print(json.dumps(gpus, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
