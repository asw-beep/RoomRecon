# src/reconstruction/mesh

**Responsibility:** derive an exportable surface from the Gaussian scene.

Owns surface extraction and export to OBJ / GLB / PLY, with **point-cloud export as the
guaranteed fallback** when meshing produces poor results.

This module is explicitly secondary (ADR-001). Its failure mode is "the user doesn't get a
mesh" — never "the reconstruction broke". Nothing in `gaussian/` may import from here, and
disabling this module entirely must leave the product fully functional.

Quality expectations shown to the user must be honest. A mediocre mesh presented as a
finished asset is worse than an accurate warning.

Inputs: a trained Gaussian scene.
Outputs: mesh files, or a point cloud, or a clean "not available" state.

Tier: T1.
Milestone: M6.
