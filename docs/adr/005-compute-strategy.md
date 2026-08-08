# ADR-005 — Compute Strategy: Three-Tier Local / Free-Cloud / Campus

- **Status:** Accepted
- **Date:** 2026-08-08
- **Supersedes:** none
- **Related:** ADR-004 (pose source), `docs/compute-assessment.md`

## Context

The primary development machine is a Windows 11 laptop with an **NVIDIA RTX 3050 Laptop
GPU, 6 GB VRAM** (driver 581.86, verified 2026-08-08). WSL2 Ubuntu-22.04 and Docker
Desktop are installed. `cmake`, `conda`, COLMAP and the CUDA toolkit are not.

Two facts drive this decision.

**First, the project is not uniformly GPU-hungry.** Splitting the milestones by actual
compute need:

| Stage | GPU need | Fits in 6 GB? |
|---|---|---|
| M2 capture analysis, frame extraction | none | yes |
| M3 poses (COLMAP) | light / optional | yes |
| M3 poses (ORB-SLAM3) | none, but needs Linux | yes, under WSL2 |
| M4 3DGS training | heavy | **marginal — the pinch point** |
| M5 API + browser viewer | rendering only | yes |
| M6 mesh export | light | yes |
| M7 NeRF baseline | heavy + long | **no** |
| M7 Instant-NGP baseline | heavy | uncertain |

The majority of the engineering — the entire product layer, which is what distinguishes
this project from a research reproduction — has no meaningful GPU requirement.

**Second, 6 GB is below what reference 3DGS setups assume** (typically 12–24 GB). Standard
3DGS is plausible at reduced image resolution with capped densification, but this is an
*estimate, not a measurement*, and M1 exists to replace it with real numbers.

Relying on a single machine therefore puts the two heaviest milestones (M4, M7) on the
narrowest resource, with no fallback if the estimate is wrong.

## Decision

Adopt a **three-tier compute strategy**. Every stage names the tier it runs on, and the
pipeline is written so that tier is a configuration choice, not a code fork.

### Tier 1 — Laptop, inside WSL2 Ubuntu-22.04 (primary)

The daily driver. Runs M2, M3, M5, M6 and all product/API/viewer work, plus M4 at reduced
settings once M1 establishes what fits.

Reconstruction work happens **inside WSL2, not native Windows**. CUDA reaches through the
Windows driver; COLMAP and ORB-SLAM3 build with their normal Linux instructions. This
avoids the Windows build tarpit (Pangolin, DBoW2, g2o) entirely. Source files stay on the
Windows filesystem; the editor stays on Windows.

### Tier 2 — Kaggle Notebooks (heavy training)

Runs M4 3DGS training and the M7 experiments. Chosen over Colab because it offers a
weekly GPU quota with 16 GB cards (P100 / 2×T4) and, decisively, **headless background
execution** for up to 12 hours via Save & Run All — training does not require a live
browser session.

16 GB removes the VRAM constraint from M4 and M7, giving a working fallback if the 6 GB
estimate proves wrong.

Google Colab is retained as a secondary interactive tier for short spikes and debugging.
Lightning AI Studios is noted as a fallback where a *persistent filesystem* is needed.

### Tier 3 — Campus machine (requested, not assumed)

To be requested with an explicit specification: **≥12 GB VRAM, Linux, SSH access, Docker
or sudo, persistent storage.** If granted, it hosts long unattended runs and the M7 NeRF
baseline. Its absence must not block any milestone.

### Binding constraints this imposes

1. **SLAM stays on Tier 1.** ORB-SLAM3 takes 20+ minutes to build from scratch and neither
   Kaggle nor Colab persists between sessions. Rebuilding per session would consume the
   GPU quota doing CPU work. Poses are computed locally and uploaded as artifacts.
2. **Checkpoint/resume is mandatory, not optional.** Tier 2 sessions are time-capped and
   can be pre-empted. Any training run that cannot resume from a checkpoint is a defect.
3. **Every heavy stage is a headless script.** A Tier 2 session must be reducible to
   `git clone && setup.sh && train.py --config ...`. No interactive-only steps, no manual
   notebook cell ordering.
4. **The tier boundary is an artifact boundary.** Data crossing tiers must be a versioned
   artifact conforming to the schemas in `docs/data-contracts.md` — frames, poses, sparse
   points going up; Gaussian scene and metrics coming back. Artifacts must be small enough
   to move over a normal connection.
5. **Free tiers are not a demo dependency.** The final demo must run from local artifacts.

## Consequences

**Positive**

- Risk #1 (6 GB insufficient for 3DGS) gains a zero-cost fallback instead of being
  project-ending.
- The product layer develops in parallel with, and independent of, GPU availability.
- Forcing headless, checkpointed, artifact-boundaried stages is good engineering
  regardless of where the code runs — it makes M9 reproducibility largely free.
- Recorded numbers will span two hardware profiles, which strengthens M7 and M8 reporting.

**Negative**

- Two environments to keep working, and to keep in sync. Environment drift becomes a real
  failure mode.
- Artifact transfer adds friction and manual steps to the M4 loop.
- Free-tier quotas and availability are outside our control; sustained heavy usage may be
  throttled.
- Benchmark numbers must always be reported *with the tier stated*, or they are
  meaningless. Never compare a Tier 1 timing against a Tier 2 timing without saying so.

**Neutral**

- Adds a second environment-verification target to M1 (see M1 tasks).

## Alternatives considered

**Laptop only.** Rejected. Puts M4 and M7 on 6 GB with no fallback, and makes the NeRF
baseline in M7 impractical. Would likely force cutting M7 entirely.

**Cloud only.** Rejected. No persistence means rebuilding the toolchain every session;
ORB-SLAM3 becomes untenable; interactive viewer development becomes needlessly awkward;
and the demo would depend on a free service being available on the day.

**Paid GPU rental (RunPod / Vast.ai).** Deferred, not rejected. Cheap and effective, and
worth keeping as an escape hatch if free quotas prove insufficient during M7. Not adopted
now because the project should not require spending to reach its gates.

**Wait for campus access before starting.** Rejected. Availability is uncertain and
outside our control; blocking on it risks the semester timeline.

## Notes

The VRAM figures for 3DGS in this document are estimates from reference implementations,
not measurements on this hardware. **M1 replaces them with measured values.** If the
measured Tier 1 ceiling makes M4 unworkable locally, 3DGS training moves permanently to
Tier 2 and this ADR is amended rather than the milestone being descoped.

Evaluate **gsplat** (nerfstudio) alongside the original INRIA CUDA rasterizer during M1.
It is reported to be more memory-efficient and is better packaged, which matters
disproportionately at 6 GB.
