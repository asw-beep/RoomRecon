# ADR-008 — Phone Depth as an Optional Input, RGB-Only as the Fallback (amends ADR-002, ADR-006)

- **Status:** 🔶 **Proposed**, pending G1 review. ADR-002 remains in force until this is
  approved.
- **Date:** 2026-09-25
- **Amends:** ADR-002 (monocular RGB input), ADR-006 (phone-tracked poses) ·
  **Related:** ADR-001, ADR-007

## Context

ADR-002 excluded depth because it "restricts users to recent high-end phones". ADR-006
kept that exclusion: capture-app exports provide poses, but no depth enters reconstruction.

The team's priority is now smooth, good-quality room reconstruction. The best evidence on
what achieves that indoors comes from DN-Splatter (Turkulainen et al., arXiv 2403.17822). It
was evaluated on MuSHRoom, the dataset M1 is moving to. **All numbers below are theirs, on
their hardware and settings. They show direction and are not our targets.**

- Depth supervision was the largest single improvement to 3DGS indoors. On MuSHRoom
  vr_room, mesh F-score went from 56.3 to 86.6 when the depth loss was added (their
  Table 4).
- Depth from the phone's sensor clearly beat depth estimated from RGB. On ScanNet++
  b20a261fdf, F-score was 0.58 with iPhone sensor depth, against 0.22 at best from a
  monocular network (their Table 8).
- Monocular depth still helped novel views when captures were sparse (their Table 14).

The phones that have a depth sensor (LiDAR on iPhone Pro models) are a minority, so
requiring depth would still break ADR-002's accessibility premise. Ignoring depth when a
phone provides it for free, in the same capture-app export, leaves the biggest measured
quality gain unused.

## Decision (proposed)

**Depth is optional. It is used when the capture provides it, and the pipeline never
requires it.**

| Input | Reconstruction uses |
|---|---|
| Capture-app export **with** depth (e.g. a LiDAR iPhone) | RGB + device poses + **sensor depth** as a training prior |
| Capture-app export **without** depth | RGB + device poses (ADR-006, preferred path) |
| Plain RGB video | RGB only (ADR-002 fallback path, poses per ADR-004) |

Rules:

1. **Missing depth never fails a job.** The same pipeline and outputs run without it. Each
   stage decides from the validated input manifest (M2), never by probing files mid-run.
2. **Depth is validated like any other input.** Resolution, alignment to the RGB frame,
   invalid-pixel fraction and a plausible range are checked. Depth that fails validation
   is dropped with a recorded reason, and the job continues RGB-only. **Bad depth never
   silently degrades a scene.**
3. **Every artifact records which path produced it.** `scene.json` and
   `reconstruction_metrics.json` state `depth_source: sensor | none` (and later
   `monocular` if adopted). Results from different paths are never compared without
   saying so.
4. **Depth is a training prior, not ground truth.** Sensor depth is noisy at edges (the
   DN-Splatter paper makes the same point). It enters as a weighted loss and is never
   copied into geometry directly.
5. **The RGB-only path keeps working and stays tested.** It is the default for most users.
   Its quality is reported separately, never lifted by numbers from the depth path.

**Scale:** sensor depth is metric, and so are ARKit poses (ADR-006). This still does
**not** license centimeter-accurate measurement, which stays out of scope for v1. Any UI
wording about scale follows ADR-006's rule: measured before claimed.

## Consequences

**Positive**

- The largest measured indoor quality gain becomes available at no extra user effort,
  whenever the phone has the sensor.
- Plain walls, the failure case M1 found, are exactly where depth helps most.
- Depth-supervised Gaussians lie closer to real surfaces, which should make M6 mesh
  export more useful (M6 must measure this, not assume it).

**Negative**

- **Two quality tiers.** Users with LiDAR phones get better rooms. The product must be
  clear about this and not present the depth path's quality as what everyone gets.
- More to validate and test: a depth corpus, depth validation rules, and the drop-to-RGB
  path must each be exercised.
- The trainer needs a depth-supervision loss that gsplat 1.5.3's example trainer does not
  provide. Its `depth_loss` uses sparse SfM points, not dense depth maps. That means
  another patch to maintain, or a small trainer extension of our own.
- Export formats differ between capture apps (Polycam, Record3D, NeRFCapture). The
  importer targets formats, not apps (ADR-006), and depth adds one more field to map.

**Neutral**

- ADR-002's scale statement stays true for the RGB-only path.
- The M1 MuSHRoom experiment is unaffected: its 8 runs are RGB-only. MuSHRoom ships
  iPhone depth, so it can later test this ADR's depth path on the same rooms.

## Alternatives considered

**Stay RGB-only (ADR-002/006 as written).** Rejected by the team: it forgoes the largest
measured quality gain for the users who can get it for free.

**Require depth.** Rejected: it excludes most phones and breaks ADR-002's accessibility
premise.

**Monocular depth estimates only (e.g. Depth Anything) for everyone.** Not rejected. It is
the candidate prior for the RGB-only path and belongs in M4. It is weaker than sensor depth
in the evidence above, so it does not replace sensor depth where that exists.

## Evidence required before approval

1. On MuSHRoom (vr_room, koivu), the same room trained RGB-only and with sensor depth, and
   evaluated on the separate test walk. Report the quality difference with its tier.
2. A capture with no depth and a capture with deliberately corrupted depth both finish
   RGB-only, each with a recorded reason.
