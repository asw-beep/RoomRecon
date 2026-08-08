# Contributing to RoomRecon

## The framing that matters

RoomRecon is a **product**, not a paper reproduction. The source papers answer *"what
techniques exist?"* This project answers *"how does a person actually use them?"*

Work is framed as *"the user uploads a video and gets a room they can walk through"* —
never as *"implement 3DGS."*

## Frozen decisions

Settled. Change them by writing a new ADR, not by editing code around them. See
[`docs/adr/`](docs/adr/README.md) for the reasoning and costs.

| Decision | Choice |
|---|---|
| Primary scene representation | 3D Gaussian Splatting |
| Mesh | Derived / secondary export, never blocking |
| Input | Monocular RGB video only |
| NeRF / Instant-NGP | Experimental baselines, isolated and non-blocking |
| Architecture | Modular monolith |
| Backend | FastAPI + Python orchestration |
| Frontend | React + Three.js / R3F |
| Storage | SQLite + local filesystem |
| Jobs | Simple local background worker |
| Scale | Internally consistent, **not** metric |
| Compute | Three tiers: WSL2 laptop / Kaggle / campus |

## Working rules

**Hard gates.** "The code runs" does not close a milestone. A stage closes with tests,
validation against stated criteria, documented failure cases, and updated docs. Do not
start stage N+1 while stage N is open.

**One milestone at a time.** No speculative scaffolding for future milestones.

**No fabricated numbers.** Every performance target is `TBD — <milestone> baseline` until
measured. Never copy a figure from a paper into our requirements. Never state a metric that
was not run.

**Every measurement carries its tier.** T1 (laptop, 6 GB) and T2 (Kaggle, 16 GB) numbers
are not comparable. Presenting one against the other without saying so is a defect.

**Failure paths are features.** Bad input rejected with an actionable reason is worth more
than a lucky reconstruction. "Bad input silently produces bad output" is the
highest-impact risk in the register.

**Determinism.** Same video + same config + same pipeline version → reproducible result
within stated numerical variation. Seed everything, version configs, stamp the pipeline
version into every artifact.

**Observability.** Every job carries `job_id`, stage, status, duration, error, GPU memory,
CPU, and output artifact paths.

## Module boundaries

Enforced by discipline — nothing at runtime prevents a bad import, so watch for it in
review.

- `src/` **never** imports `experiments/`. If research code becomes valuable enough to
  ship, it is rewritten into `src/` with tests and a gate — never promoted by import.
- `reconstruction/gaussian/` **never** imports `reconstruction/mesh/`. The secondary path
  cannot endanger the primary one.
- Artifacts crossing a module or tier boundary conform to
  [`docs/data-contracts.md`](docs/data-contracts.md).
- External CUDA rasterizers are called, never rewritten.

## Compute tiers

| | Where | Runs |
|---|---|---|
| **T1** | Laptop, WSL2 Ubuntu-22.04, 6 GB | Daily driver; all product work. **SLAM is T1-only** |
| **T2** | Kaggle, 16 GB, headless 12 h | Heavy 3DGS training and all experiments |
| **T3** | Campus machine, ≥12 GB | Requested, not assumed. Never a blocker |

Consequences: **checkpoint/resume is mandatory** (T2 sessions are pre-emptible); heavy
stages must run headless as `git clone && setup.sh && train.py --config ...`; the tier
boundary is an artifact boundary; **the final demo runs from local artifacts** and never
depends on a free service being up.

## Git conventions

Branches: `main`, `feat/<area>`, `exp/<baseline>`.

Commit prefixes: `feat:` `fix:` `test:` `docs:` `exp:`

Commits are scoped and small. No "implemented whole project" commits.

## Out of scope for v1

Native mobile app · auth / multi-user · cloud GPU infrastructure · real-time
phone-to-server reconstruction · collaboration · semantic segmentation · object
recognition or labeling · object-level editing · dynamic scenes and moving people · CAD
reconstruction · centimeter-accurate measurement · multi-room mapping.

Requests for these get pointed at the milestone that would have to land first.
