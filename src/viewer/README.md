# src/viewer

**Responsibility:** the thing the user actually experiences. Everything upstream exists to
feed this.

React + Three.js / React Three Fiber. Owns the splat renderer, orbit and walk navigation,
reset, camera-path playback, the reconstruction metadata panel, and — critically —
loading, progress, empty and error states. **A blank screen on failure is a product bug**,
not an edge case.

Risk #3 lives here: generating a `.ply` is not a product. If the browser cannot render the
scene smoothly, the architecture changes, not the expectations. LOD and compression are on
the table from M5 onward.

Rendering is far cheaper than training — this runs fine on the user's machine, and the
tier model does not apply. But viewer FPS is a measured baseline like any other.

Inputs: a Gaussian scene + metadata over the `src/api` surface.
Outputs: an interactive room.

Tier: T1 / the user's browser.
Milestone: M5.
