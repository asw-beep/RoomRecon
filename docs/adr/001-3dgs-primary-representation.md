# ADR-001 — 3D Gaussian Splatting as the Primary Scene Representation

- **Status:** Accepted
- **Date:** 2026-08-08
- **Related:** ADR-002 (monocular input), ADR-005 (compute strategy)

## Context

RoomRecon must give a non-expert user an indoor scene they can *interactively explore in a
browser*. That product requirement — interactive, in a browser, on ordinary hardware —
constrains the scene representation more than reconstruction quality alone would.

The candidate representations from the source papers:

| Representation | Novel views | Interactive render | Training cost | Fits our product? |
|---|---|---|---|---|
| Mesh + texture | Limited fidelity | Excellent | Moderate | Poor visual fidelity for cluttered rooms |
| NeRF | Excellent | No — volume rendering is slow | Very high | No |
| Instant-NGP | Very good | Better, still not trivial in-browser | Moderate | Marginal |
| **3D Gaussian Splatting** | **Excellent** | **Yes — rasterization** | **Moderate** | **Yes** |

3DGS is architecturally aligned with what we need: it initializes from the sparse points
that camera calibration already produces, optimizes an explicit set of Gaussians with
density control, and renders through a visibility-aware rasterizer designed for real-time
novel-view synthesis. The pipeline we would build for pose estimation feeds it directly.

NeRF's continuous neural field is the conceptual foundation for all of this, but its
rendering cost makes it a poor fit for a product whose core interaction is "move around
the room."

## Decision

**3D Gaussian Splatting is the primary scene representation.** It is what the user
interacts with, what the viewer renders, and what "a completed reconstruction" means.

Three consequences are binding:

1. **Mesh is a derived, secondary representation.** Geometry export exists for users who
   need an asset for other software. `src/reconstruction/mesh/` may read the Gaussian
   scene; nothing in `gaussian/` may depend on it. Disabling mesh entirely must leave the
   product fully functional.

2. **NeRF and Instant-NGP are experimental baselines only.** They live in `experiments/`,
   are never imported by `src/`, and cannot block any gate. If neither ever runs
   successfully, RoomRecon still ships.

3. **The viewer is not optional.** A `.ply` written to disk does not satisfy this ADR. The
   representation is only justified if it renders interactively, which is why Risk #3 is
   treated as architecture-killing and probed at M1 rather than discovered at M5.

## Consequences

**Positive**

- Real-time browser rendering is achievable, which is the whole product premise.
- Sparse-point initialization means the tracking and reconstruction stages compose
  naturally — less integration risk than a representation needing different inputs.
- Explicit Gaussians are inspectable and exportable; a neural field is neither.
- Training cost is within reach of free-tier GPUs (ADR-005).

**Negative**

- VRAM scales with Gaussian count, which is exactly where our 6 GB local constraint bites.
- Scene files are large relative to a mesh; the viewer may need LOD or compression.
- Mesh extraction from Gaussians is less mature than from a density field, so M6 quality
  is genuinely uncertain — hence its secondary status and point-cloud fallback.
- We depend on external CUDA rasterizers we do not maintain.

**Neutral**

- Commits us to the 3DGS ecosystem's tooling and file formats.

## Alternatives considered

**Mesh as primary.** Rejected. Photometric fidelity in cluttered indoor scenes is poor,
and the product's value proposition is visual faithfulness, not geometry.

**NeRF as primary.** Rejected. Rendering cost is incompatible with interactive browser
exploration. Retained as a baseline for M7 because it is the conceptual reference point.

**Instant-NGP as primary.** Rejected, but less firmly. Fast to train and far better than
NeRF at render time, yet still awkward to serve interactively in a browser, and its output
is not directly exportable. Retained as the more interesting of the two baselines.

**Point cloud as primary.** Rejected as a product, kept as the guaranteed export fallback.
Visually unconvincing as "a room you can walk through."
