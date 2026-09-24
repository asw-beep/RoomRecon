# RoomRecon — Milestone Roadmap

Derived from `Plan/Plan1.txt` and `Plan/Plan2.txt`. Each milestone lists executable tasks,
the tests that must pass, and the gate criteria. **A milestone is not closed because the
code runs.** It closes when the gate criteria are demonstrated with artifacts.

Legend: `[ ]` not started · `[~]` in progress · `[x]` gate passed

---

## M0 — Architecture Freeze  ·  Gate G0

Goal: turn the plan documents into a real, navigable repository with decisions recorded.

Tasks
- [x] `git init`, `.gitignore` (storage/, *.ply, *.mp4, venv, __pycache__, node_modules)
- [x] Create the directory skeleton, each package with a `README.md` stating its one
      responsibility
- [x] `docs/architecture/system.md` — data flow from MP4 to viewer, artifact at each hop
- [x] ADRs: 001 3DGS primary · 002 monocular RGB input · 003 modular monolith ·
      005 compute strategy · 004 pose source **opened and deferred to M1 evidence**
- [x] `docs/dependency-inventory.md` — every external dep, license, install path,
      whether it needs CUDA, whether it builds on Windows, which tier it runs on
- [x] `docs/compute-assessment.md` — 6 GB VRAM budget: what fits, what must be downscaled
- [x] `docs/data-contracts.md` — schemas for `scene.json`, `camera_poses.json`,
      `reconstruction_metrics.json`, and the on-disk project layout
- [x] Risk register as a living file, `docs/risks.md`
- [x] Root `README.md`

Gate G0 — every major component is justified in writing; a reader can trace a video
through the whole system on paper; the ADRs exist; the dependency inventory is complete.

**Gate status: awaiting review.** One documented deviation — the inventory lists
dependencies, licenses and tiers but **versions are `TBD — M1`, not concrete**. Pinning a
version without having installed it would be a fabricated number, which the project rules
forbid. Versions are pinned during M1 installation. Accept this deviation or M0 cannot
close without installing the toolchain, which is M1's work.

---

## M1 — Reconstruction Toolchain  ·  Gate G1  ⚠ highest-risk milestone

Goal: prove the stack runs on **both compute tiers** defined in ADR-005 — locally in WSL2,
and on a cold-start Kaggle session — and that artifacts move cleanly between them. This
milestone exists to kill the project early if neither tier can carry it. Build nothing on
top until it passes.

Compute tiers (see `docs/adr/005-compute-strategy.md`):
**T1** laptop / WSL2 Ubuntu-22.04, 6 GB · **T2** Kaggle, 16 GB headless · **T3** campus
machine, requested not assumed.

### T1 — laptop environment (WSL2)
- [x] Stand up WSL2 Ubuntu-22.04; verify GPU passthrough (`nvidia-smi` inside WSL)
- [x] Pin a real Python env, 3.10/3.11 via conda or uv — the 3.12 WindowsApps stub is not
      viable for the 3DGS ecosystem
- [x] Install CUDA toolkit matching driver 581.86; verify `torch.cuda.is_available()`
- [x] Install COLMAP; run on a small public image set → sparse model
- [x] Build ORB-SLAM3; run on a TUM or EuRoC sequence → trajectory.
      **ORB-SLAM3 is T1-only** — it is never rebuilt on T2 (ADR-005 constraint 1)
- [x] Train 3DGS on one known-good small scene end to end at reduced settings
- [~] ~~Evaluate **gsplat** vs the original INRIA rasterizer for memory footprint at 6 GB~~
      **Proposed drop, for G1 review.** The question behind it — does 3DGS fit in 6 GB —
      is answered: gsplat trains 1M Gaussians in ~2.2 GB on T1. gsplat is kept because
      its MCMC strategy gives a hard Gaussian cap (bounded VRAM), it is Apache-2.0 where
      INRIA is non-commercial, and it is what the resume patch targets. Building a second
      CUDA extension to measure a constraint that no longer binds is not worth the time
- [x] **Record peak VRAM, wall-clock time, and the exact settings that made it fit**
- [x] Render the trained scene in a browser splat viewer at a measured FPS

### T2 — Kaggle environment (cold start)
- [ ] `scripts/setup_t2.sh` — clone → deps → build CUDA extensions, from a bare session
- [ ] Train the **same** scene on T2; record VRAM, time, and settings for comparison
- [ ] Prove headless background execution (Save & Run All) completes without a live session
- [ ] Prove **checkpoint/resume**: kill a run mid-training, resume from checkpoint, finish.
      This is a gate requirement, not a nice-to-have (ADR-005 constraint 2)
- [ ] Measure total setup time and count it against the weekly GPU quota

### Tier boundary
- [ ] Define the upload artifact (frames + poses + sparse) and the download artifact
      (Gaussian scene + metrics) against `docs/data-contracts.md`
- [ ] Measure artifact sizes; confirm they move over a normal connection
- [ ] Document the round trip in `docs/tier-handoff.md` — exact commands, both directions
- [ ] Every heavy stage runnable as `git clone && setup.sh && train.py --config ...`,
      no interactive-only steps (ADR-005 constraint 3)

### Decisions and tooling
- [ ] Write `docs/adr/004-pose-source.md` with the decision the T1 evidence supports
- [~] `scripts/verify_env.py` — one command, runs on **both** tiers, prints a pass/fail
      dependency table and identifies which tier it is on
- [ ] Request the T3 campus machine with the ADR-005 spec (≥12 GB VRAM, Linux, SSH,
      Docker/sudo, persistent storage). Do not block on the answer.

Gate G1 — a controlled scene goes images → poses → sparse → Gaussians → browser render,
**on T1 and on T2**, with measured VRAM/time/FPS recorded separately for each tier. The
checkpoint/resume cycle is demonstrated. The artifact round trip is documented and
executed at least once. If the scene does not fit in 6 GB on T1, the fallback is chosen
and written into ADR-005 **before** M2 begins.

Baselines established: 3DGS training time (per tier), peak VRAM (per tier), viewer FPS,
T2 cold-start setup cost.

**Reporting rule from here on:** every performance number is recorded with its tier. A
T1 timing compared against a T2 timing without stating both is a defect.

---

## M2 — Input Pipeline  ·  Gate G2

Goal: arbitrary user video → validated, deterministic, reconstruction-ready frame set.

Tasks
- [ ] `src/capture/` — probe MP4: codec, resolution, FPS, duration, rotation, EXIF/intrinsics
- [ ] Validation rules with explicit rejection reasons (too short, too low-res, wrong codec,
      corrupt, variable frame rate)
- [ ] Quality metrics: blur (variance of Laplacian), exposure/histogram, feature density
      (ORB/SIFT count), inter-frame overlap, camera motion magnitude, coverage estimate
- [ ] Composite capture-quality score + **actionable** user recommendations
      ("move closer to the rear wall for 3–5 more seconds")
- [ ] `src/preprocessing/` — frame extraction and keyframe selection (blur-aware,
      overlap-aware), deterministic under a fixed seed and config
- [ ] Build a small test corpus: good, blurry, dark, fast-motion, low-coverage, no-loop,
      texture-poor
- [ ] Tests: rejection cases assert the right reason; same video twice → byte-identical
      frame manifest

Gate G2 — every bad input in the corpus is rejected with a correct, human-readable reason;
every good input yields a deterministic frame set; the quality report is reproducible.

Baseline established: video processing time.

---

## M3 — Camera Reconstruction  ·  Gate G3

Goal: stable camera trajectory and sparse map from a real room video.

Tasks
- [ ] Camera intrinsics: from EXIF where available, calibration target otherwise; document
      the fallback when neither exists
- [ ] Integrate the pose source chosen in ADR-004 behind a `PoseEstimator` interface so the
      other one remains swappable
- [ ] Emit `camera_poses.json` + sparse point cloud in the frozen schema
- [ ] Tracking-failure detection: lost frames, drift, failed loop closure — surfaced as job
      errors, not silent bad output
- [ ] Trajectory visualization for debugging
- [ ] Write the capture protocol doc (walk speed, loop back to start, lighting, distance)
- [ ] Tests: known sequence → trajectory within tolerance of ground truth; deliberately
      broken sequence → clean, reported failure

Gate G3 — a full room loop produces a coherent trajectory without catastrophic tracking
loss, and failures are reported rather than silently degraded.

Baselines established: SLAM/SfM processing time, tracking success rate.

---

## M4 — First 3DGS Reconstruction  ·  Gate G4  ★ first major milestone

Goal: our own room, reconstructed from our own phone video, explorable.

Tasks
- [ ] Pose/image validation gate before training (count, coverage, intrinsics sanity)
- [ ] Initialize Gaussians from the sparse points
- [ ] 3DGS training wrapper, tier-selectable by config (`configs/t1_6gb.yaml`,
      `configs/t2_16gb.yaml`), checkpointing and resume — resume is mandatory, T2 sessions
      are pre-emptible (ADR-005)
- [ ] Export the scene (`.ply` / splat format) + `reconstruction_metrics.json`
- [ ] Held-out view evaluation: PSNR/SSIM on test frames
- [ ] Log peak VRAM, iterations, Gaussian count, wall-clock time **and tier** per run
- [ ] Tests: pipeline runs headless end to end on a fixture; artifacts match schema

Gate G4 — a real smartphone video of a real room becomes a Gaussian scene we can load and
interactively explore. Quality is honestly reported, including where it is bad.

Baselines established: 3DGS training time, scene size, first PSNR/SSIM numbers.

---

## M5 — Product Viewer  ·  Gate G5

Goal: turn the reconstruction into something a person uses, not a file they download.

Tasks
- [ ] React + R3F app; splat renderer; orbit and walk modes; reset; camera-path playback
- [ ] Reconstruction metadata panel (frames, keyframes, tracking status, scene status)
- [ ] Loading, progress, empty and error states — no blank screen on failure
- [ ] FastAPI endpoints per the frozen API surface; background job worker with real states
      (queued/running/failed/complete) and progress
- [ ] SQLite project store + `storage/projects/<id>/` layout
- [ ] Measure viewer FPS and load time; add LOD/compression if the scene stalls the browser
- [ ] Tests: API contract tests; a smoke test that uploads a fixture and reaches `complete`

Gate G5 — someone who knows nothing about SLAM or splatting uploads a video, watches
progress, and explores the room. Measured FPS recorded.

Baseline established: viewer FPS.

---

## M6 — Geometry Export  ·  Gate G6

Goal: mesh as a *secondary* representation that never endangers the primary path.

Tasks
- [ ] Extract geometry from the Gaussian scene (surface extraction / TSDF / Poisson)
- [ ] Export OBJ / GLB / PLY, plus point-cloud export as the guaranteed fallback
- [ ] Export UI in the viewer, with honest quality expectations shown to the user
- [ ] Tests: exports load in a standard 3D tool; mesh failure leaves the 3DGS scene intact

Gate G6 — mesh export works, and disabling or failing it changes nothing about the 3DGS
experience.

---

## M7 — Representation Experiments  ·  Gate G7

Goal: a fair, reproducible comparison. Lives entirely in `experiments/`.

**Runs on T2/T3.** NeRF is impractical on 6 GB and its training time exceeds what a laptop
session should absorb. All three baselines must be trained on the **same tier** or the
comparison is invalid.

Tasks
- [ ] One shared harness: same images, same poses, same train/test split, same metrics,
      same tier
- [ ] NeRF baseline (accept it may be slow — it is not on the critical path)
- [ ] Instant-NGP baseline
- [ ] 3DGS through the same harness
- [ ] Report PSNR, SSIM, LPIPS, training time, render FPS, memory — **with tier and
      hardware stated on every row**
- [ ] Budget the run against the T2 weekly quota before starting; split across sessions
      with checkpoints if it will not fit
- [ ] `docs/experiments/comparison.md` + the raw numbers, re-runnable by one command

Gate G7 — another person can re-run the comparison and get the same conclusions. All three
baselines ran on the same tier. No numbers quoted from papers as if they were ours.

---

## M8 — Robustness Evaluation  ·  Gate G8

Goal: know and state exactly when RoomRecon fails. This is worth more than a pretty demo.

Tasks
- [ ] Run the full pipeline across the M2 corpus: good, blurry, low-light, fast motion,
      low coverage, no loop, texture-poor
- [ ] Record per-condition: tracking success, reconstruction success, quality, time,
      failure mode
- [ ] Correlate the M2 capture-quality score against actual outcomes — does the gate
      predict failure? Tune it with this evidence.
- [ ] `docs/evaluation/robustness.md` — the operating envelope, stated plainly

Gate G8 — we can say, with data, which captures work and which do not, and the capture
quality gate demonstrably catches the bad ones.

Baseline established: reconstruction success rate.

---

## M9 — Product Hardening  ·  Gate G9

Goal: a clean machine reproduces the whole project from the docs.

Tasks
- [ ] Job state machine with retries, resume after interruption, artifact cleanup
- [ ] Structured logging; per-job resource metrics; config validation on startup
- [ ] Performance profiling pass; fix the worst bottleneck found
- [ ] Docs: README, architecture, setup, API, configuration, pipeline, evaluation
      methodology, troubleshooting
- [ ] Repeatable install (env file + script, or a container); CI running the test suite
- [ ] Convert every `TBD` in the metrics table to a measured value
- [ ] Final demo path and STAR write-up

Gate G9 — a fresh machine, following only the documentation, installs the project, runs
the tests, and reconstructs a room.

---

## Metrics table

Fill in as each baseline lands. Never invent a value. **Every row records its tier** —
T1 (laptop/WSL2, 6 GB) or T2 (Kaggle, 16 GB). A number without a tier is meaningless.

| Metric | Tier | Target | Established at |
|---|---|---|---|
| Video processing time | T1 | TBD | M2 |
| Pose estimation time | T1 | TBD | M3 |
| 3DGS training time | T1 | TBD | M1 / M4 |
| 3DGS training time | T2 | TBD | M1 / M4 |
| Peak VRAM | T1 | TBD | M1 / M4 |
| Peak VRAM | T2 | TBD | M1 / M4 |
| T2 cold-start setup cost | T2 | TBD | M1 |
| Scene size | — | TBD | M4 |
| Viewer FPS | T1 | TBD | M1 / M5 |
| PSNR / SSIM / LPIPS | T2 | TBD | M7 |
| Tracking success rate | T1 | TBD | M3 |
| Reconstruction success rate | T1 | TBD | M8 |

## Risks to attack early

1. **Can 6 GB run 3DGS?** → M1. *Mitigated by ADR-005* — T2 (16 GB) is the fallback, so
   this is no longer project-ending, but it still decides where M4 lives permanently.
2. **Can we get reliable poses from handheld phone video?** → M1/M3. Architecture-killing,
   and **not** mitigated by the tier strategy — SLAM is T1-only by design.
3. **Can the browser render the scene interactively?** → M1 spike, M5 proper.
   Architecture-killing — a `.ply` on disk is not a product. Tier-independent: the viewer
   runs on the user's machine, not ours.
4. **Environment drift between T1 and T2.** New with ADR-005. Mitigated by
   `scripts/verify_env.py` running identically on both tiers.
