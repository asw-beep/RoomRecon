#!/usr/bin/env python3
"""Fetch a reference scene at a pinned revision and fingerprint it.

    python scripts/fetch_scene.py --dest /tmp/data/deepblending            # download
    python scripts/fetch_scene.py --verify /tmp/data/deepblending/db/drjohnson  # fingerprint only

The mirror is third-party, so it is pinned to a commit: an upstream edit cannot silently
change the data between tiers or runs. The fingerprint (sha256 over every file's relative
path + sha256) goes into the session artifact; equal fingerprints on T1 and T2 prove both
trained on the same bytes. An attached Kaggle dataset is fingerprinted the same way.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ID = "alexmkwizu/gaussian_training_datasets"
REVISION = "f63877dbf97e58cbf9f9ad15d0aae7548e502098"   # pinned 2026-09-25
SCENES = {"drjohnson": {"path": "db/drjohnson", "images": 263}}   # 263: counted on T1 in M1


def fingerprint(scene_dir: Path) -> dict:
    files = sorted(p for p in scene_dir.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(scene_dir).as_posix().encode())
        h.update(hashlib.sha256(p.read_bytes()).digest())
    images = scene_dir / "images"
    return {"files": len(files), "images": len(list(images.iterdir())) if images.is_dir() else 0,
            "has_sparse": (scene_dir / "sparse").is_dir(), "sha256": h.hexdigest()}


def validate(name: str, fp: dict) -> list:
    want = SCENES[name]
    errors = []
    if not fp["has_sparse"]:
        errors.append("no sparse/ (COLMAP poses)")
    if fp["images"] != want["images"]:
        errors.append(f"{fp['images']} images, expected {want['images']}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", default="drjohnson", choices=sorted(SCENES))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dest", type=Path, help="download into <dest>/<scene path>")
    g.add_argument("--verify", type=Path, help="fingerprint an existing scene dir")
    ap.add_argument("--json-out", type=Path, help="also write the fingerprint here")
    args = ap.parse_args()

    if args.dest:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=REPO_ID, repo_type="dataset", revision=REVISION,
                          allow_patterns=[SCENES[args.scene]["path"] + "/**"],
                          local_dir=str(args.dest), max_workers=8)
        scene_dir = args.dest / SCENES[args.scene]["path"]
        source = {"repo": REPO_ID, "revision": REVISION}
    else:
        scene_dir, source = args.verify, {"local": str(args.verify)}

    fp = {"scene": args.scene, "dir": str(scene_dir), "source": source, **fingerprint(scene_dir)}
    fp["errors"] = validate(args.scene, fp)
    print(json.dumps(fp, indent=2))
    if args.json_out:
        args.json_out.write_text(json.dumps(fp, indent=2))
    return 1 if fp["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
