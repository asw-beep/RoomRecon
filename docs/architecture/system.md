# RoomRecon — System Architecture

The purpose of this document is that a reader can follow one video through the entire
system on paper, and know what exists at every hop.

## 1. System overview

```
┌─────────────────────────────────────────────────────────────┐
│  WEB CLIENT — React + Three.js / R3F          src/viewer/   │
│  upload · progress · interactive scene · export             │
└───────────────────────────┬─────────────────────────────────┘
                            │  REST (+ polling / WebSocket)
┌───────────────────────────▼─────────────────────────────────┐
│  BACKEND — FastAPI                              src/api/    │
│  projects · uploads · job orchestration · artifact serving  │
└───────────────────────────┬─────────────────────────────────┘
                            │  in-process job worker
┌───────────────────────────▼─────────────────────────────────┐
│  RECONSTRUCTION CORE                                        │
│                                                             │
│  capture → preprocessing → tracking → sparse → gaussian     │
│                                              └──→ mesh      │
└─────────────────────────────────────────────────────────────┘
             │                                    │
      SQLite (metadata)              storage/projects/<id>/ (artifacts)
```

One process, strict internal boundaries (ADR-003). The module structure is the shape a
service split would take if one were ever needed.

## 2. The journey of one video

Every hop names its module, its output artifact, and how it fails.

### Hop 1 — Upload
`POST /projects` then `POST /projects/{id}/upload` → `src/api/`

The file lands at `storage/projects/<id>/input/room.mp4`. A project row is created in
SQLite. Nothing is processed yet.

*Fails when:* the file is not a video, or exceeds size limits. → 4xx, no job created.

### Hop 2 — Validation and capture quality
`src/capture/` → **`quality_report.json`**

Probes codec, resolution, FPS, duration, rotation, and any EXIF intrinsics. Then measures
blur, exposure, feature density, inter-frame overlap, camera motion, and coverage, and
composes a score with actionable recommendations.

*Fails when:* the video is corrupt, too short, too low-resolution, or scores below
threshold. → **rejected with a human-readable reason before any GPU time is spent.** This
is the gate that prevents the register's highest-impact risk: bad input silently producing
bad output.

### Hop 3 — Frame extraction and keyframe selection
`src/preprocessing/` → `frames/` + **`frame_manifest.json`**

Extracts frames, then selects keyframes — dropping blurred ones and redundant ones while
keeping enough baseline between views.

**Determinism contract:** same video + same config + same seed → byte-identical manifest.
Everything downstream inherits reproducibility from this hop.

*Fails when:* too few usable frames survive selection. → job failed, reason reported.

### Hop 4 — Camera pose estimation
`src/tracking/` → **`camera_poses.json`** + sparse points

Resolves intrinsics (EXIF → calibration target → documented fallback), then estimates
poses through the `PoseEstimator` interface. COLMAP and ORB-SLAM3 both sit behind it;
ADR-004 picks the default at M1 from measured evidence.

**T1 only** (ADR-005) — ORB-SLAM3 takes 20+ min to build and cloud tiers do not persist.

*Fails when:* tracking is lost, drift is excessive, or loop closure fails. → **reported as
a job error, never silently degraded into a bad reconstruction.**

### Hop 5 — Sparse validation
`src/reconstruction/sparse/` → validated sparse cloud

Converts pose output into the trainer's expected format and sanity-checks point count,
spatial extent, and per-view visibility.

*Fails when:* the sparse model is too thin to initialize from. → job failed. Catching this
here saves an hour of doomed training.

### Hop 6 — Gaussian training
`src/reconstruction/gaussian/` → **`scene.ply`** + **`reconstruction_metrics.json`**

Initializes Gaussians from sparse points and optimizes with density control. Config
selects the tier budget: `t1_6gb.yaml` or `t2_16gb.yaml` — same code path, different
budgets.

**Checkpoint and resume are mandatory.** T2 sessions are time-capped and pre-emptible.

Logs peak VRAM, iterations, Gaussian count, wall-clock time, and tier for every run.

*Fails when:* VRAM is exhausted or the run is interrupted. → resume from checkpoint.

### Hop 7a — Interactive viewing *(primary)*
`src/viewer/` via `GET /projects/{id}/scene`

The user orbits, walks, replays the camera path, and reads reconstruction metadata.
**This is the product.** Everything above exists to reach this hop.

*Fails when:* the scene is too large for the browser. → LOD / compression. Risk #3, probed
at M1 rather than discovered here.

### Hop 7b — Geometry export *(secondary)*
`src/reconstruction/mesh/` via `GET /projects/{id}/export`

Surface extraction → OBJ / GLB / PLY, with point-cloud export as the guaranteed fallback.

*Fails when:* meshing quality is poor. → export the point cloud instead. **Failure here
never affects 7a** (ADR-001).

## 3. Storage layout

```
storage/projects/<project_id>/
├── input/          room.mp4
├── frames/         extracted + selected frames
├── poses/          camera_poses.json
├── sparse/         sparse point cloud
├── gaussian/       scene.ply, checkpoints
├── mesh/           exported geometry (optional)
├── metrics/        reconstruction_metrics.json, timings
└── metadata.json   scene.json + pipeline version + config hash
```

Artifacts on the filesystem, metadata in SQLite (ADR-003). Every artifact is stamped with
the pipeline version and config hash that produced it, so any scene can be traced back to
its inputs.

## 4. Job model

Reconstruction is a job, not an HTTP request.

```
queued → running → complete
            ↓
          failed  → (resumable from last checkpoint)
```

Every job carries `job_id`, current stage, status, duration, error, GPU memory, CPU, and
output artifact paths. This is the observability contract — and it is what makes Gate G9
reachable.

## 5. Compute tiers (ADR-005)

| Tier | Where | Runs |
|---|---|---|
| **T1** | Laptop, WSL2 Ubuntu-22.04, 6 GB | Hops 1–5, 7a, 7b; hop 6 at reduced settings |
| **T2** | Kaggle, 16 GB, headless 12 h | Hop 6 full runs; all M7 experiments |
| **T3** | Campus machine, ≥12 GB | Requested, not assumed. Long runs, NeRF baseline |

**The tier boundary is an artifact boundary.** Only schema-conforming artifacts cross it:
frames + poses + sparse go up, Gaussian scene + metrics come back. Every performance
number is reported with its tier.

## 6. Module boundary rules

- `src/` **never** imports `experiments/`. Research code is quarantined.
- `gaussian/` **never** imports `mesh/`. The secondary path cannot endanger the primary.
- Artifacts crossing module or tier boundaries conform to `docs/data-contracts.md`.
- External CUDA rasterizers are called, never rewritten.

## 7. What this architecture deliberately does not have

No microservices, no Postgres, no object storage, no Redis/Celery, no Kubernetes, no auth.
Each was considered and rejected in ADR-003 because it solves a problem this project does
not have. The seams exist if that changes.
