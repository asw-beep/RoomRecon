# src/capture

**Responsibility:** decide whether a user's video is worth reconstructing, and tell them
why if it isn't.

Owns video probing (codec, resolution, FPS, duration, rotation, EXIF/intrinsics),
validation with explicit rejection reasons, and the capture-quality metrics: blur,
exposure, feature density, inter-frame overlap, camera motion, coverage. Produces a
composite score and **actionable** recommendations.

This module exists to stop the highest-impact failure in the risk register — bad input
silently producing bad output. It runs before any GPU time is spent.

Inputs: an uploaded video file.
Outputs: a capture-quality report, or a rejection with a human-readable reason.

Tier: T1. No GPU required.
Milestone: M2.
