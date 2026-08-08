# src/reconstruction/gaussian

**Responsibility:** train the 3D Gaussian Splatting scene. This is the heart of the
product.

Owns Gaussian initialization from sparse points, the training loop wrapper, density
control, scene export, and per-run resource accounting.

Hard requirements:

- **Tier-selectable config.** `configs/t1_6gb.yaml` and `configs/t2_16gb.yaml` — the same
  code path, different budgets (ADR-005).
- **Checkpoint and resume are mandatory.** T2 sessions are time-capped and pre-emptible.
  A training run that cannot resume is a defect, not a limitation.
- **Every run logs peak VRAM, iterations, Gaussian count, wall-clock time, and tier.** A
  number without its tier is meaningless.

We call out to CUDA rasterizers; we do not write them. Evaluate gsplat against the
original INRIA implementation at M1 — memory efficiency matters disproportionately at 6 GB.

Inputs: poses + frames + sparse points.
Outputs: Gaussian scene (`.ply`/splat) + `reconstruction_metrics.json`.

Tier: T1 at reduced settings, T2 for full runs.
Milestone: M4.
