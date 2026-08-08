# ADR-002 — Monocular RGB Video as the Only Input

- **Status:** Accepted
- **Date:** 2026-08-08
- **Related:** ADR-001, ADR-004 (pose source)

## Context

The value proposition is *"make visually rich indoor 3D reconstruction accessible using
commodity RGB video"* — explicitly not *"replace LiDAR scanners."* Anyone with a phone
should be able to use RoomRecon without special hardware.

ScanNet, one of our source papers, built its dataset from RGB-**D** capture. That
difference matters: depth removes scale ambiguity and improves geometry substantially.
Adopting RGB-D would make reconstruction easier and would exclude most users.

Modern phones do carry IMUs, and visual-inertial SLAM can make metric scale observable —
ORB-SLAM3's central contribution is in that space. But accessing IMU streams
time-synchronized with video is not something a user can do by recording a normal video,
and building a capture app is out of scope for v1.

## Decision

**RoomRecon v1 accepts monocular RGB video and nothing else.** No depth, no LiDAR, no IMU,
no multi-camera rig. A file a phone's stock camera app produces is the entire input
contract.

The unavoidable consequence, stated plainly rather than hidden:

> **RoomRecon v1 guarantees an internally consistent reconstruction, not
> centimeter-accurate metric dimensions.**

Scale is unobservable from monocular video alone. We do not approximate it, infer it from
assumed object sizes, or present arbitrary units as measurements. If a user needs real
dimensions, the honest answer is that v1 does not provide them.

This must be visible in the product UI, not buried in documentation.

## Consequences

**Positive**

- Zero hardware barrier — the largest possible user base.
- One input format means one validation path, one preprocessing path, one test corpus.
  The pipeline stays simple enough to actually finish in a semester.
- Aligns with 3DGS, which consumes posed RGB images natively.

**Negative**

- **No metric scale.** This is a real product limitation and the honest framing costs us a
  use case (measurement) we might otherwise claim.
- Monocular tracking is fragile. Texture-poor walls, fast motion, and low light degrade
  pose estimation far more than RGB-D would — which is precisely why `src/capture` exists
  and why M8 robustness evaluation matters.
- Geometry quality is lower than a depth-sensing pipeline would achieve. Affects M6 mesh
  quality most.

**Neutral**

- Makes ScanNet a methodology and evaluation reference rather than a runtime dependency.

## Alternatives considered

**RGB-D input.** Rejected for v1. Better reconstruction, metric scale, easier tracking —
but it contradicts the accessibility premise and restricts users to recent high-end
phones. Listed as the first future extension.

**Visual-inertial (RGB + IMU).** Rejected for v1 with some regret. It would make scale
observable, which is the single biggest limitation above. Requires a custom capture app
with synchronized streams — a project in itself. Revisit if a native app is ever in scope.

**User-provided scale reference.** Deferred, not rejected. Asking the user to enter one
known dimension, or place a reference object, would resolve scale cheaply. Not in the v1
scope but the most likely path to metric output, and a good candidate for v1.1.

**Multi-video / multi-session capture.** Rejected. Multi-room and session merging are
explicitly out of scope.
