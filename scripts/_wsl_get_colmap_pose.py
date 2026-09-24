"""scratch - extracts real camera poses from the COLMAP model so the browser spike can be
framed from a viewpoint the scene was actually trained on, instead of a guessed one.

gsplat normalises the scene when loading (Parser(normalize=True)), so raw COLMAP poses are
reported here alongside the transform the viewer needs.
"""
import numpy as np
import sys

sys.path.insert(0, "/home/aswin/roomrecon/toolchain/gsplat/examples")
from datasets.colmap import Parser

parser = Parser(data_dir="/home/aswin/roomrecon/work/south-building-960", factor=1, normalize=True)

camtoworlds = parser.camtoworlds  # [N,4,4] in the SAME normalised space gsplat trained in
print(f"cameras: {len(camtoworlds)}")

positions = camtoworlds[:, :3, 3]
print(f"camera position bounds: min={np.round(positions.min(0), 3)} max={np.round(positions.max(0), 3)}")
print(f"camera centroid       : {np.round(positions.mean(0), 3)}")

# scene point cloud in the same space
pts = parser.points
print(f"points: {len(pts)}")
print(f"points p5 : {np.round(np.percentile(pts, 5, axis=0), 3)}")
print(f"points p95: {np.round(np.percentile(pts, 95, axis=0), 3)}")
print(f"points median: {np.round(np.median(pts, axis=0), 3)}")

# emit a few concrete poses for the viewer
print("\n=== sample poses (position, forward, up) ===")
for i in [0, len(camtoworlds) // 3, 2 * len(camtoworlds) // 3]:
    c2w = camtoworlds[i]
    pos = c2w[:3, 3]
    fwd = c2w[:3, 2]      # COLMAP/OpenCV camera looks down +Z
    up = -c2w[:3, 1]      # and +Y is down
    tgt = pos + fwd * float(np.linalg.norm(np.median(pts, axis=0) - pos))
    print(f"cam[{i}] pos={np.round(pos,3).tolist()} lookAt={np.round(tgt,3).tolist()} up={np.round(up,3).tolist()}")
