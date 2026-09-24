"""Extracts a good default viewer camera from a COLMAP scene, in the SAME normalised space
gsplat trains in. Avoids the two traps found earlier:
  - up-axis is scene-dependent (+Z for COLMAP), not a guess
  - min/max point bounds are inflated by outliers; percentiles give the real content extent
"""
import sys
import numpy as np

sys.path.insert(0, "/home/aswin/roomrecon/toolchain/gsplat/examples")
from datasets.colmap import Parser

data_dir = sys.argv[1] if len(sys.argv) > 1 else "/home/aswin/roomrecon/datasets/deepblending/db/drjohnson"
p = Parser(data_dir=data_dir, factor=1, normalize=True)

c2w = p.camtoworlds
pts = p.points
print(f"cameras={len(c2w)} points={len(pts)}")

lo, hi = np.percentile(pts, 2, axis=0), np.percentile(pts, 98, axis=0)
center = (lo + hi) / 2
extent = hi - lo
print(f"content p2 ={np.round(lo,3).tolist()}")
print(f"content p98={np.round(hi,3).tolist()}")
print(f"center={np.round(center,3).tolist()} extent={np.round(extent,3).tolist()}")

# average camera up across the rig: -Y of camera frame is world up in COLMAP convention
ups = -c2w[:, :3, 1]
up = ups.mean(0)
up /= np.linalg.norm(up)
print(f"scene up axis ~ {np.round(up,3).tolist()}")

# pick the camera whose view direction best faces the content centre
best, best_d = None, -2
for i in range(len(c2w)):
    pos, fwd = c2w[i, :3, 3], c2w[i, :3, 2]
    v = center - pos
    nv = np.linalg.norm(v)
    if nv < 1e-6:
        continue
    d = float(np.dot(fwd / np.linalg.norm(fwd), v / nv))
    if d > best_d:
        best_d, best = d, i

pos = c2w[best, :3, 3]
print(f"\nbest-facing camera index {best} (alignment {best_d:.3f})")
print("VIEWER_POS  =", np.round(pos, 4).tolist())
print("VIEWER_LOOK =", np.round(center, 4).tolist())
print("VIEWER_UP   =", np.round(up, 4).tolist())
