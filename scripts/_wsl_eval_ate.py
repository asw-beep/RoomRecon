"""scratch - absolute trajectory error for a monocular TUM-format trajectory.

Monocular scale is unobservable, so the estimate is aligned to ground truth with a
Sim(3) Umeyama fit before computing ATE. The fitted scale is reported, not hidden.
Coverage (fraction of the ground-truth time span the estimate spans) is reported too:
ORB-SLAM3 saves only the active map, so a tracking loss shows up as low coverage
rather than as a large error.

usage: python _wsl_eval_ate.py <groundtruth.txt> <KeyFrameTrajectory.txt> [max_dt=0.02]
prints one JSON line.
"""
import json
import sys

import numpy as np


def load(path):
    rows = []
    for line in open(path):
        if line.startswith("#") or not line.strip():
            continue
        v = line.split()
        rows.append([float(x) for x in v[:4]])
    return np.array(rows)


def associate(gt, est, max_dt):
    pairs = []
    for i, t in enumerate(est[:, 0]):
        j = np.searchsorted(gt[:, 0], t)
        cands = [k for k in (j - 1, j) if 0 <= k < len(gt)]
        k = min(cands, key=lambda k: abs(gt[k, 0] - t))
        if abs(gt[k, 0] - t) <= max_dt:
            pairs.append((i, k))
    return pairs


def umeyama_sim3(src, dst):
    """Returns s, R, t minimising ||dst - (s R src + t)||."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    var_s = (xs ** 2).sum() / len(src)
    s = np.trace(np.diag(D) @ S) / var_s
    t = mu_d - s * R @ mu_s
    return s, R, t


def main():
    gt, est = load(sys.argv[1]), load(sys.argv[2])
    max_dt = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
    pairs = associate(gt, est, max_dt)
    out = {"keyframes": len(est), "matched": len(pairs)}
    if len(pairs) < 3:
        out["error"] = "fewer than 3 associated poses"
        print(json.dumps(out))
        return
    src = np.array([est[i, 1:4] for i, _ in pairs])
    dst = np.array([gt[k, 1:4] for _, k in pairs])
    s, R, t = umeyama_sim3(src, dst)
    err = np.linalg.norm(dst - (s * (R @ src.T).T + t), axis=1)
    gt_span = gt[-1, 0] - gt[0, 0]
    out.update({
        "ate_rmse_m": round(float(np.sqrt((err ** 2).mean())), 4),
        "ate_mean_m": round(float(err.mean()), 4),
        "ate_median_m": round(float(np.median(err)), 4),
        "ate_max_m": round(float(err.max()), 4),
        "sim3_scale": round(float(s), 4),
        "gt_path_length_m": round(float(np.linalg.norm(np.diff(gt[:, 1:4], axis=0), axis=1).sum()), 3),
        "coverage": round(float((est[-1, 0] - est[0, 0]) / gt_span), 3),
        "init_delay_s": round(float(est[0, 0] - gt[0, 0]), 2),
    })
    print(json.dumps(out))


if __name__ == "__main__":
    main()
