# src/preprocessing

**Responsibility:** turn an accepted video into a deterministic set of frames suitable for
pose estimation.

Owns frame extraction and keyframe selection — blur-aware and overlap-aware, so we keep
sharp frames with enough baseline between them and drop redundant or unusable ones.

**Determinism is the contract.** The same video with the same config and seed must produce
a byte-identical frame manifest. Everything downstream inherits its reproducibility from
this module.

Inputs: a validated video + the capture-quality report from `src/capture`.
Outputs: extracted frames on disk + a frame manifest recording exactly what was selected
and why.

Tier: T1. No GPU required.
Milestone: M2.
