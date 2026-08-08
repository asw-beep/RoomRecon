# src/reconstruction/sparse

**Responsibility:** produce and validate the sparse point cloud that initializes the
Gaussians.

3DGS starts from sparse points recovered during camera calibration. This module owns that
handoff: converting whatever the pose source emits into the format the Gaussian trainer
expects, and sanity-checking it (point count, spatial extent, per-view visibility) before
expensive training begins.

A bad sparse model produces a bad Gaussian scene an hour later. Catch it here.

Inputs: pose-estimation output from `src/tracking`.
Outputs: a validated sparse point cloud in the frozen schema.

Tier: T1.
Milestone: M3–M4.
