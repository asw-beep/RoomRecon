# src/tracking

**Responsibility:** recover where the camera was for every frame.

Owns camera intrinsics resolution (EXIF, calibration target, or documented fallback) and
pose estimation behind a `PoseEstimator` interface. The interface exists so COLMAP and
ORB-SLAM3 stay swappable — ADR-004 picks the production default at M1 based on measured
evidence, and the loser remains available.

Also owns tracking-failure detection: lost frames, drift, failed loop closure. **Failures
are reported as job errors, never silently degraded into a bad reconstruction.**

Inputs: the frame set from `src/preprocessing`.
Outputs: `camera_poses.json` + a sparse point cloud, or a reported tracking failure.

Tier: **T1 only.** ORB-SLAM3 takes 20+ min to build and cloud tiers do not persist, so
poses are always computed locally and uploaded as artifacts (ADR-005).
Milestone: M3.
