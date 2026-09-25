# ADR-007 — Kaggle as the Primary Compute Tier (amends ADR-005)

- **Status:** 🔶 **Proposed**, pending G1 review. ADR-005 remains in force until this is
  approved.
- **Date:** 2026-09-25
- **Amends:** ADR-005 (compute strategy) · **Related:** ADR-004 (pose source), ADR-006
  (phone-tracked poses)

## Context

ADR-005 made the laptop (T1) the daily driver. T1 ran M2, M3, M5 and M6, plus M4 at
reduced settings. Kaggle (T2) was reserved for heavy M4 training and M7.

Three things changed during M1:

1. **The T2 path works end to end.** T2 run 2 (2026-09-25, Kaggle T4 ×2 with 1 used,
   `docs/m1-downloads.csv`) passed every gate check from a generated notebook with no manual
   steps. It covered setup, environment verification, a 15k-step drjohnson baseline and a
   SIGKILL/resume check. The same `train.py` and configs run on both tiers.
2. **The laptop toolchain was deleted in the 2026-09-25 reset.** Keeping T1 able to
   reconstruct means rebuilding and maintaining a second environment. ADR-005 already named
   environment drift as a cost, and it caused a real incident (the torch upgrade in the M1
   log).
3. **ADR-006 (proposed) takes ORB-SLAM3 off the preferred path.** ADR-005 kept SLAM on T1
   because ORB-SLAM3 can't be rebuilt in every session. If poses come from the phone,
   that reason no longer shapes where the pipeline runs.

The team's direction: do the heavy lifting on Kaggle, with **at least 80% of the pipeline's
compute** there. The laptop is used to work with the outputs.

## Decision

**Kaggle (T2) is the primary compute tier. The laptop (T1) is the interaction tier.**

| Work | Tier |
|---|---|
| 3DGS training, evaluation, resume (M4) | T2, GPU session |
| Sparse reconstruction: COLMAP triangulation with fixed poses (ADR-006), or full SfM on the fallback path | T2 |
| Frame extraction and capture-quality analysis for a reconstruction job (M2) | T2 |
| Mesh extraction (M6) | T2 |
| NeRF / Instant-NGP / 3DGS comparison (M7), robustness sweeps (M8) | T2 |
| Viewer, API, UI, export, sending jobs to T2 and collecting results, inspecting results, writing code, unit tests | T1 |
| ORB-SLAM3 | T1 only, experimental. Not on the production path if ADR-006 is accepted |

### The 80% target is measured

- **Metric:** the share of pipeline stage wall-clock time that ran on T2. Stage time comes
  from `stages.jsonl` and `run.json`, which T2 already writes. Editing, code writing and
  unit tests are development, not pipeline compute, and are not counted.
- **Needed for this:** any pipeline stage run on T1 must record its time the same way.
  The observability contract (`docs/architecture/system.md`) already requires this.
- **Reported at each gate** as T2 seconds over total seconds, over the milestone's runs.
  Target ≥ 80%. The current value is `TBD — first gate after acceptance`.

### ADR-005 constraints, restated

1. **SLAM** can no longer justify keeping reconstruction local. If ADR-006 is **rejected**,
   this ADR has to be revisited: the fallback pose source would then decide whether
   production poses can be produced on T2 at all.
2. **Checkpoint/resume is mandatory.** Unchanged, and more important now that T2 carries
   everything. Resuming across sessions (`push.sh push --continue`) must be demonstrated,
   not assumed.
3. **Every heavy stage is a headless script.** Unchanged: `git clone && setup && run`.
4. **The tier boundary moves upstream.** What goes **up** is now the raw input (video or a
   capture-app export). What comes **down** is the Gaussian scene, mesh and metrics.
   Both remain versioned, schema-conforming artifacts.
5. **Free tiers are not a demo dependency.** Unchanged. The demo loads scenes that were
   already reconstructed and stored locally. The laptop never needs Kaggle to *show* a
   room.

### The app sends reconstruction to T2

The product keeps "upload a video, get a room". `POST /projects/{id}/reconstruct` on the
local API starts a T2 job through the Kaggle API. This is the same push → status → fetch
cycle as `scripts/kaggle/m1_t2/push.sh`, driven by the local job worker (ADR-003):
- `GET /projects/{id}/status` shows the T2 state (queued, running, complete, error),
  along with the stage records.
- The fetched scene and metrics land in `storage/projects/<id>/`.

**This lifts "cloud GPU infrastructure" from the v1 out-of-scope list** (`CONTRIBUTING.md`), but only for this
single-user dispatch to T2. Multi-user use, hosted serving and paid cloud GPUs stay out of
scope. Constraint 5 still holds: a scene that is already stored locally never needs Kaggle
to be viewed.

### CPU-only stages on T2

Stages that need no GPU should run in a Kaggle session **without** a GPU accelerator, so
they don't use up the weekly GPU quota. Whether CPU sessions really are free of GPU quota,
and how fast COLMAP runs there, is `TBD — verify on the Kaggle quota page and in the first
T2 sparse run`.

## Consequences

**Positive**

- One reconstruction environment to maintain instead of two. The laptop keeps no CUDA
  build, and environment drift between tiers stops being a failure mode.
- VRAM stops being a constraint for M4, M6 and M7 (16 GB against 6 GB).
- Every run is already headless, recorded and judged by `t2_verdict.py`, so the evidence
  trail comes for free.
- The laptop's GPU and disk (the E:-only budget) go to the viewer, which M1 showed is the
  real bottleneck at 1M splats.

**Negative**

- **Iteration is slower.** Every change is a commit, push, queue, cold start and fetch.
  Setup alone took 336 s in run 2 (T2), about 14% of that run's stage time. Caching the
  built environment would cut this; not yet measured.
- **We depend on quota.** The weekly GPU quota is outside our control. The current weekly
  use is `TBD — track from run 2 onward`. Paid rental (ADR-005 alternatives) stays the
  escape hatch.
- **There is no local fallback for reconstruction.** If Kaggle is down or the quota is
  spent, no new scene can be made until it comes back. Existing scenes stay viewable.
- **The app now depends on an external service for new scenes.** The local API needs a
  Kaggle token on the laptop, a job can wait in Kaggle's queue, and a failure there must
  show up as a job error with a reason, not as a job that hangs.
- **Uploads get bigger.** Raw video goes up instead of frames and poses. Sizes are
  `TBD — M2`.
- **G1 changes.** "On T1 and on T2" becomes: reconstruction on T2, and viewing plus the
  artifact round trip on T1. The pre-reset T1 training numbers stay in the log as history.
  They are not a gate requirement.

**Neutral**

- `scripts/setup_t1.sh` is kept, but T1 reconstruction is no longer exercised at gates.

## Alternatives considered

**Keep ADR-005 as written (T1 as daily driver, T1 reconstruction at reduced settings).**
Rejected by the team. It keeps two reconstruction environments in sync after T2 has shown
it can carry the work alone.

**Kaggle for everything, including the viewer and demo.** Rejected. Kaggle can't host an
interactive web app, and ADR-005 constraint 5 (the demo never depends on a free service)
still holds.

**Paid GPU rental as the primary tier.** Deferred, as in ADR-005. It stays the escape
hatch if the free quota can't sustain M7.
