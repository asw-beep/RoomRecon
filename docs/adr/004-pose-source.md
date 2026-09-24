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

| Measurement (all T1) | COLMAP | ORB-SLAM3 |
|---|---|---|
| Builds and runs on T1 (WSL2) | ✅ apt 3.7, CPU-only build, no patches | ✅ after 3 local patches (C++17, monocular-only targets, upstream `LoopClosing.h` bool→int bug) + a headless patch |
| Wall-clock time on the reference scene | 128 images @960 px: extract 33 s, **exhaustive** match ~23 min, map 3.1 min. Exhaustive is O(n²); video needs the sequential matcher | TUM fr1_xyz 798 frames: 39 s. fr3_long_office 2585 frames: 115–120 s (~17–18 ms/frame, real time) |
| Trajectory quality vs ground truth (TUM) | not measured (COLMAP not yet run on TUM) | Sim(3)-aligned keyframe ATE RMSE: fr1_xyz 9.3 / 9.3 / 9.0 mm; fr3_long_office 10.4 / 20.2 / 14.3 mm over a 22 m loop. 3 runs each, 1 map, 0 resets; ~2× run-to-run spread (nondeterministic) |
| Behaviour on a real handheld room loop | **TBD — needs a phone video of a room** | **TBD — same video** |
| Loop closure on a returning walk | n/a | ✅ detected in 3/3 fr3_long_office runs |
| Output → 3DGS conversion effort | none: gsplat reads `sparse/0` directly (proven on south-building and drjohnson) | not yet tried. Outputs keyframe poses only, no 3DGS-ready points; needs COLMAP triangulation from fixed poses or an exported map |
| Failure mode when tracking degrades | not yet observed | per-run nondeterminism above; a monocular init delay (3.5 s on fr1_xyz) loses the opening frames |

Numbers and sources: `docs/m1-downloads.csv`. Nothing here is decided yet. The handheld
row is the one that matters, since it is the product input and TUM is not.

## Decision criteria

The production default is whichever **more reliably produces usable poses from real
handheld phone video of a real room** — not whichever is faster, and not whichever is more
impressive to write about. Risk #2 (unreliable poses) is architecture-killing and is *not*
mitigated by the cloud tier, so robustness outweighs everything else here.

If neither is reliable on real captures, that is a finding that changes the capture
protocol or the product scope, and it must surface at M1 rather than M3.
