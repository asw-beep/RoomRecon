# ADR-004 — Production Pose Source: COLMAP vs ORB-SLAM3

- **Status:** 🔶 **Proposed — decision deferred to M1 evidence**
- **Date opened:** 2026-08-08
- **Related:** ADR-002 (monocular input), ADR-005 (compute strategy)

> This ADR is deliberately unresolved. It is recorded now so the question is visible and
> the interface is designed for it, but **it will not be decided by assumption.** M1
> produces the measurements; this document is then completed and moved to Accepted.

## Context

The engineering plan names ORB-SLAM3 as the core pose source with COLMAP as the fallback.
Two facts complicate that ordering.

**Arguments for COLMAP as production default**

- 3DGS natively consumes COLMAP sparse output. Choosing it removes a conversion layer that
  would otherwise sit on the critical path.
- Working Windows builds exist; ORB-SLAM3 effectively requires WSL2 or Docker.
- Offline global bundle adjustment is generally more robust than incremental tracking on
  handheld footage with erratic motion.
- No real-time constraint applies — the user has already uploaded a file and is waiting on
  a job.

**Arguments for ORB-SLAM3 as production default**

- Native keyframe selection, loop closing, and relocalization — a room walk that returns to
  its starting point is exactly the loop-closure case it is built for.
- Produces a genuine camera trajectory, which the viewer's camera-path feature wants.
- Far faster than exhaustive SfM on long sequences.
- It is a source paper for this project, and using it meaningfully strengthens the
  technical narrative.

**The realistic synthesis**, pending evidence: COLMAP as the production pose source,
ORB-SLAM3 for keyframe selection, trajectory, and the real-time story. But this is a
hypothesis, not the decision.

## Decision (pending)

Not yet made. What *is* decided now:

1. **Both sit behind a `PoseEstimator` interface** in `src/tracking/`. Whichever loses
   remains available and swappable by config.
2. **Both are built and measured at M1** on the same controlled scene.
3. **Pose estimation is T1-only** regardless of the outcome (ADR-005): ORB-SLAM3 takes
   20+ minutes to build and cloud tiers do not persist.

## Evidence required from M1

| Measurement | COLMAP | ORB-SLAM3 |
|---|---|---|
| Builds and runs on T1 (WSL2) | TBD | TBD |
| Wall-clock time on the reference scene | TBD | TBD |
| Trajectory quality vs ground truth (TUM/EuRoC) | TBD | TBD |
| Behaviour on a real handheld room loop | TBD | TBD |
| Loop closure on a returning walk | n/a | TBD |
| Output → 3DGS conversion effort | TBD | TBD |
| Failure mode when tracking degrades | TBD | TBD |

## Decision criteria

The production default is whichever **more reliably produces usable poses from real
handheld phone video of a real room** — not whichever is faster, and not whichever is more
impressive to write about. Risk #2 (unreliable poses) is architecture-killing and is *not*
mitigated by the cloud tier, so robustness outweighs everything else here.

If neither is reliable on real captures, that is a finding that changes the capture
protocol or the product scope, and it must surface at M1 rather than M3.
