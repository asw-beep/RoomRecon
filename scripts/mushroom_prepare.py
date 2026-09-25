#!/usr/bin/env python3
"""MuSHRoom iPhone room -> two COLMAP-format datasets over the same images (ADR-006 test).

    python scripts/mushroom_prepare.py <room>/iphone <out>/<room> --vocab-tree <file.bin>

Both datasets share one feature extraction and one set of matches, so the pose source is
the only difference between them:

  device/  Polycam's phone-tracked poses, taken as given. COLMAP only triangulates points,
           with every pose held fixed, and the script checks that no pose moved.
  sfm/     COLMAP's own image-only reconstruction (mapper): what the plain-video fallback
           path (ADR-002/004) would produce. Images it cannot register are recorded, not hidden.

Evaluation follows MuSHRoom (Ren et al., WACV 2024): train on the long capture minus the
frames in its test.txt ("val"), and test a second time on the separate short capture
("xseq", a different walk). The test sets hold only frames that BOTH datasets registered,
so the two pose sources are scored on the same views.

Conventions, verified on the data (depth reprojection, see docs/m1-downloads.csv):
  - transformations*.json hold camera->world 4x4 in the OpenGL camera frame (x right,
    y up, z back); flipping y and z gives COLMAP's OpenCV frame.
  - Short-capture poses come from the dataset's transformations_colmap.json. Polycam
    tracked the short walk in its own session frame; the authors registered it into the
    long capture's frame. A test view needs a pose in the training frame, so this is the
    only way to place it, and it is recorded as the test-pose source.

Both datasets triangulate from all their registered images, test views included. That
is the usual SfM protocol for novel-view benchmarks, and it is the same for both.
Standard library + numpy + COLMAP (CLI) only.
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import numpy as np

GL_TO_CV = np.diag([1.0, -1.0, -1.0])


# --------------------------------------------------------------------------- inputs

def load_frames(path: Path) -> dict:
    """transformations*.json -> {frame stem: {"c2w": 4x4 (OpenGL), "K": (fx, fy, cx, cy, w, h)}}.

    Per-frame intrinsics win; the file's top-level values are the fallback."""
    d = json.loads(path.read_text())
    out = {}
    for fr in d["frames"]:
        g = lambda k: fr.get(k, d.get(k))  # noqa: E731
        stem = Path(fr["file_path"]).stem
        out[stem] = {"c2w": np.array(fr["transform_matrix"], dtype=float),
                     "K": tuple(float(g(k)) for k in ("fl_x", "fl_y", "cx", "cy", "w", "h"))}
    return out


def colmap_pose(c2w_gl: np.ndarray):
    """OpenGL camera->world -> COLMAP (qvec w x y z, tvec) of world->camera, OpenCV frame."""
    R_c2w = c2w_gl[:3, :3] @ GL_TO_CV
    R = R_c2w.T
    t = -R @ c2w_gl[:3, 3]
    return rot_to_qvec(R), t


def rot_to_qvec(R: np.ndarray) -> np.ndarray:
    """Rotation matrix -> unit quaternion (w, x, y, z), w >= 0 (COLMAP's convention)."""
    m = R
    tr = np.trace(m)
    if tr > 0:
        s = 2.0 * np.sqrt(tr + 1.0)
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    q /= np.linalg.norm(q)
    return q if q[0] >= 0 else -q


def qvec_to_rot(q) -> np.ndarray:
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def num(xs) -> str:
    """Plain decimal numbers for COLMAP text files. repr() of a NumPy 2 scalar prints
    'np.float64(0.35)', which COLMAP cannot parse."""
    return " ".join(repr(float(x)) for x in xs)


def camera_line(cam_id: int, w: int, h: int, fx, fy, cx, cy) -> str:
    return f"{cam_id} PINHOLE {w} {h} {num([fx, fy, cx, cy])}\n"


def image_lines(image_id: int, q, t, cam_id: int, name: str) -> str:
    """One posed image with no 2D points: header line + empty points line."""
    return f"{image_id} {num(q)} {num(t)} {cam_id} {name}\n\n"


def image_name(prefix: str, stem: str) -> str:
    """Long and short captures reuse frame names, so each gets a prefix (L_ / S_)."""
    return f"{prefix}_{stem}.jpg"


# --------------------------------------------------------------------------- COLMAP text model

def read_images_txt(path: Path) -> dict:
    """images.txt -> {name: {"q": qvec, "t": tvec, "obs": #2D points with a 3D point}}.

    Each image is exactly two lines, and the second is EMPTY for an image without 2D
    points, so blank lines are data here and must not be filtered out."""
    body = [l for l in path.read_text().splitlines() if not l.startswith("#")]
    out, i = {}, 0
    while i < len(body) and body[i].strip():          # headers are never blank
        v = body[i].split()
        ids = (body[i + 1] if i + 1 < len(body) else "").split()[2::3]
        out[v[9]] = {"q": np.array([float(x) for x in v[1:5]]), "t": np.array([float(x) for x in v[5:8]]),
                     "obs": sum(1 for x in ids if x != "-1")}
        i += 2
    return out


def centre(img: dict) -> np.ndarray:
    return -qvec_to_rot(img["q"]).T @ img["t"]


def umeyama(A: np.ndarray, B: np.ndarray):
    """Similarity (s, R, t) minimising |s R A + t - B| over paired rows."""
    ma, mb = A.mean(0), B.mean(0)
    a, b = A - ma, B - mb
    U, S, Vt = np.linalg.svd(b.T @ a / len(A))
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = float((S * np.diag(D)).sum() / a.var(0).sum())
    return s, R, mb - s * R @ ma


def pose_agreement(ref: dict, est: dict) -> dict:
    """How far one model's camera centres sit from another's after the best similarity.

    Reported in the reference's units (Polycam: metres, as tracked by the phone)."""
    common = sorted(set(ref) & set(est))
    if len(common) < 3:
        return {"common_images": len(common), "note": "fewer than 3 common images"}
    A = np.array([centre(est[n]) for n in common])
    B = np.array([centre(ref[n]) for n in common])
    s, R, t = umeyama(A, B)
    err = np.linalg.norm((s * (R @ A.T)).T + t - B, axis=1)
    return {"common_images": len(common), "median_m": round(float(np.median(err)), 4),
            "p95_m": round(float(np.percentile(err, 95)), 4), "max_m": round(float(err.max()), 4)}


def build_splits(long_names, test_stems, short_names, registered: dict, both: set) -> dict:
    """Train / val / xseq image lists for one dataset.

    train: long-capture images this dataset registered, not in test.txt, and seeing at
           least one 3D point (gsplat's depth loss averages over them; zero gives NaN).
    val:   long-capture test.txt images registered by BOTH datasets.
    xseq:  short-capture images registered by BOTH datasets."""
    test = {image_name("L", s) for s in test_stems}
    train = sorted(n for n in long_names if n not in test and n in registered and registered[n]["obs"] > 0)
    dropped = sorted(n for n in long_names if n not in test and n in registered and registered[n]["obs"] == 0)
    val = sorted(n for n in long_names if n in test and n in both)
    xseq = sorted(n for n in short_names if n in both)
    return {"train": train, "val": val, "xseq": xseq, "dropped_train_no_points": dropped}


# --------------------------------------------------------------------------- driver

def run(cmd, log: Path, timings: dict, key: str):
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.run([str(c) for c in cmd], stdout=f, stderr=subprocess.STDOUT, check=True)
    timings[key] = round(time.time() - t0, 1)


def to_txt(model: Path, out: Path, timings, key):
    out.mkdir(parents=True, exist_ok=True)
    run(["colmap", "model_converter", "--input_path", model, "--output_path", out, "--output_type", "TXT"],
        out / "convert.log", timings, key)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("room", type=Path, help="<room>/iphone, holding long_capture/ and short_capture/")
    ap.add_argument("out", type=Path)
    ap.add_argument("--vocab-tree", type=Path, required=True,
                    help="COLMAP vocabulary tree: links the two captures by image retrieval")
    ap.add_argument("--overlap", type=int, default=20, help="sequential matching window")
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f"{a.out} exists - refusing to overwrite")
    if not shutil.which("colmap"):
        raise SystemExit("colmap not on PATH")

    L, S = a.room / "long_capture", a.room / "short_capture"
    long_poses = load_frames(L / "transformations.json")                 # Polycam
    short_poses = load_frames(S / "transformations_colmap.json")         # registered by the authors
    test_stems = [l.strip() for l in (L / "test.txt").read_text().split() if l.strip()]
    missing_test = [s for s in test_stems if s not in long_poses]

    img_dir, work = a.out / "images", a.out / "_colmap"
    img_dir.mkdir(parents=True)
    work.mkdir()
    timings = {}
    long_names, short_names, poses = [], [], {}
    for prefix, cap, table, names in (("L", L, long_poses, long_names), ("S", S, short_poses, short_names)):
        for stem in sorted(table):
            src = cap / "images" / f"{stem}.jpg"
            if not src.is_file():
                continue
            n = image_name(prefix, stem)
            shutil.copyfile(src, img_dir / n)
            names.append(n)
            poses[n] = table[stem]

    # one PINHOLE camera (median intrinsics), held fixed in both datasets
    Ks = np.array([poses[n]["K"] for n in long_names + short_names])
    sizes = {tuple(k[4:6]) for k in Ks}
    if len(sizes) != 1:
        raise SystemExit(f"mixed image sizes {sizes} - one camera cannot hold them")
    fx, fy, cx, cy = np.median(Ks[:, :4], 0)
    w, h = (int(x) for x in sizes.pop())
    k_spread = float(np.max(np.abs(Ks[:, :4] / np.median(Ks[:, :4], 0) - 1)))

    db = work / "db.db"
    run(["colmap", "feature_extractor", "--database_path", db, "--image_path", img_dir,
         "--ImageReader.single_camera", "1", "--ImageReader.camera_model", "PINHOLE",
         "--ImageReader.camera_params", f"{fx},{fy},{cx},{cy}", "--SiftExtraction.use_gpu", "0"],
        work / "extract.log", timings, "feature_extraction_s")
    # Sequential within each walk; vocabulary-tree loop detection links the two walks and
    # closes loops. Image-only: no pose is used for matching, so the sfm dataset stays honest.
    run(["colmap", "sequential_matcher", "--database_path", db, "--SiftMatching.use_gpu", "0",
         "--SequentialMatching.overlap", str(a.overlap), "--SequentialMatching.loop_detection", "1",
         "--SequentialMatching.vocab_tree_path", a.vocab_tree],
        work / "match.log", timings, "matching_s")

    con = sqlite3.connect(db)
    ids = dict((n, i) for i, n in con.execute("SELECT image_id, name FROM images"))
    cam_id = con.execute("SELECT camera_id FROM cameras").fetchone()[0]
    con.close()

    # ---- device: poses as given, points triangulated
    posed = work / "posed"
    posed.mkdir()
    (posed / "cameras.txt").write_text(camera_line(cam_id, w, h, fx, fy, cx, cy))
    (posed / "points3D.txt").write_text("")
    given = {}
    with open(posed / "images.txt", "w") as f:
        for n in long_names + short_names:
            q, t = colmap_pose(poses[n]["c2w"])
            given[n] = (q, t)
            f.write(image_lines(ids[n], q, t, cam_id, n))
    dev_sparse = a.out / "device/sparse/0"
    dev_sparse.mkdir(parents=True)
    run(["colmap", "point_triangulator", "--database_path", db, "--image_path", img_dir,
         "--input_path", posed, "--output_path", dev_sparse], work / "triangulate.log", timings, "triangulation_s")
    device = read_images_txt(to_txt(dev_sparse, work / "device_txt", timings, "_")/ "images.txt")
    moved = max(max(float(np.abs(qvec_to_rot(device[n]["q"]) - qvec_to_rot(given[n][0])).max()),
                    float(np.abs(device[n]["t"] - given[n][1]).max())) for n in device)
    if moved > 1e-6:   # text round-trip precision; a real pose change would be far larger
        raise SystemExit(f"POSES CHANGED during triangulation (max {moved:.2e}) - not device poses anymore")

    # ---- sfm: image-only reconstruction, same features and matches, intrinsics fixed
    sfm_all = work / "sfm_models"
    sfm_all.mkdir()
    run(["colmap", "mapper", "--database_path", db, "--image_path", img_dir, "--output_path", sfm_all,
         "--Mapper.ba_refine_focal_length", "0", "--Mapper.ba_refine_principal_point", "0",
         "--Mapper.ba_refine_extra_params", "0"], work / "mapper.log", timings, "mapper_s")
    models = []
    for m in sorted(p for p in sfm_all.iterdir() if p.is_dir()):
        imgs = read_images_txt(to_txt(m, work / f"sfm_txt_{m.name}", timings, "_") / "images.txt")
        models.append((len(imgs), m, imgs))
    models.sort(key=lambda x: -x[0])
    sfm = models[0][2] if models else {}
    sfm_sparse = a.out / "sfm/sparse/0"
    sfm_sparse.parent.mkdir(parents=True)
    if models:
        shutil.copytree(models[0][1], sfm_sparse)
    timings.pop("_", None)

    both = set(device) & set(sfm)
    report = {
        "room": a.room.parent.name, "source": str(a.room),
        "images": {"long": len(long_names), "short": len(short_names)},
        "test_txt": {"frames": len(test_stems), "missing_from_poses": missing_test},
        "camera": {"model": "PINHOLE", "w": w, "h": h, "fx": fx, "fy": fy, "cx": cx, "cy": cy,
                   "max_rel_deviation_of_per_frame_intrinsics": round(k_spread, 5)},
        "pose_sources": {"device_train": "Polycam transformations.json (long capture)",
                         "test_walk": "dataset transformations_colmap.json (short capture, in the long frame)"},
        "matching": {"sequential_overlap": a.overlap, "loop_detection": "vocab tree", "vocab_tree": a.vocab_tree.name},
        "timings_s": timings,
        "datasets": {},
    }
    for arm, reg, sparse in (("device", device, dev_sparse), ("sfm", sfm, sfm_sparse)):
        split = build_splits(long_names, test_stems, short_names, reg, both)
        d = a.out / arm
        # No images/ link here: session outputs may not keep symlinks. The consumer links
        # <arm>/images -> ../images when it unpacks the room (scripts/run_mushroom_train.sh).
        (d / "split.json").write_text(json.dumps({k: split[k] for k in ("train", "val", "xseq")}, indent=1))
        pts = sparse / "points3D.bin"
        report["datasets"][arm] = {
            "registered": {"long": sum(n in reg for n in long_names), "short": sum(n in reg for n in short_names)},
            "coverage_long": round(sum(n in reg for n in long_names) / max(1, len(long_names)), 4),
            "points3D_bin_bytes": pts.stat().st_size if pts.exists() else 0,
            "split_sizes": {k: len(split[k]) for k in ("train", "val", "xseq")},
            "dropped_train_no_points": split["dropped_train_no_points"],
        }
    report["datasets"]["device"]["max_pose_change_after_triangulation"] = moved
    report["datasets"]["sfm"]["models"] = [n for n, _, _ in models]
    report["sfm_vs_device_pose_agreement"] = pose_agreement(device, sfm)
    (a.out / "prep_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
