# src/reconstruction

**Responsibility:** turn poses and images into a scene the user can look at.

Three sub-modules, in strict priority order:

| | Module | Status |
|---|---|---|
| `sparse/` | Sparse point cloud, the initialization for Gaussians | Supporting |
| `gaussian/` | **3D Gaussian Splatting — the primary scene representation** | Core |
| `mesh/` | Surface extraction and geometry export | Secondary |

**The mesh branch must never block or degrade the Gaussian branch.** If mesh extraction
fails or is disabled, the product is unaffected. This is a frozen decision (ADR-001), not
a preference.

Inputs: `camera_poses.json` + frames + sparse points.
Outputs: a Gaussian scene (`.ply`/splat) + `reconstruction_metrics.json`; optionally a mesh.

Milestones: M4 (gaussian), M6 (mesh).
