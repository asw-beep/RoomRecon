# Compute Assessment

What fits where, and what has to give.

> ⚠️ **Everything on this page is an estimate until M1.** These figures come from
> reference implementations on other hardware. They exist to plan against, not to cite.
> M1 replaces them with measurements from this machine, and any figure that survives
> unmeasured into a report is a defect.

---

## 1. Hardware

**T1 — development laptop** (verified 2026-08-08)

```
GPU      NVIDIA GeForce RTX 3050 Laptop, 6144 MiB VRAM, driver 581.86
OS       Windows 11 + WSL2 Ubuntu-22.04
Python   3.12.10 (WindowsApps stub — must be replaced, see dependency inventory)
Node     25.6.1        ffmpeg  present
Missing  cmake, conda, COLMAP, CUDA toolkit
```

**T2 — Kaggle**: P100 16 GB or 2×T4 16 GB · 12 h session cap · weekly GPU quota ·
headless background execution · **no persistence between sessions**.

**T3 — campus machine**: requested at ≥12 GB VRAM, Linux, SSH, Docker/sudo, persistent
storage. Not assumed to exist.

---

## 2. The core problem

Reference 3DGS setups assume **12–24 GB**. T1 has **6 GB**.

VRAM during Gaussian training is driven by:

| Factor | Effect | Our lever |
|---|---|---|
| Gaussian count | Dominant, grows during densification | Cap densification; stop earlier |
| Image resolution | Per-view working memory | Downscale to ~960 px wide (`-r 2` / `-r 4`) |
| Batch / views in flight | Moderate | Keep minimal |
| Rasterizer implementation | Meaningful | **Evaluate gsplat vs INRIA at M1** |

Gaussian count is the one that actually decides whether a run fits, and it is also the one
that most directly affects visual quality. That trade is the crux of M1.

---

## 3. Estimated budget — what should fit on T1

*Planning assumptions. Not measurements.*

| Setting | T1 (6 GB) | T2 (16 GB) |
|---|---|---|
| Image resolution | ~960 px wide | Full (1080p) |
| Image count | ~100–150 | 150–300 |
| Iterations | 7k–15k | 30k |
| Densification | Capped early | Standard schedule |
| Expected outcome | A usable room, visibly softer | Reference quality |

**The honest position:** a small-to-medium room at reduced resolution with capped
densification is *plausible* on 6 GB. A large or cluttered room at full settings is not.

---

## 4. Per-stage compute profile

| Stage | Module | GPU | T1 verdict |
|---|---|---|---|
| Video validation, quality metrics | `capture/` | none | ✅ Comfortable |
| Frame extraction, keyframe selection | `preprocessing/` | none | ✅ Comfortable |
| Pose estimation — COLMAP | `tracking/` | optional | ✅ Works; CPU matching is slower |
| Pose estimation — ORB-SLAM3 | `tracking/` | none | ✅ CPU-bound; **build** is the cost, not the run |
| Sparse validation | `reconstruction/sparse/` | none | ✅ Comfortable |
| **Gaussian training** | `reconstruction/gaussian/` | **heavy** | ⚠️ **The pinch point** |
| Mesh extraction | `reconstruction/mesh/` | light | ✅ Expected fine |
| API + job worker | `api/` | none | ✅ Comfortable |
| Viewer | `viewer/` | browser GPU | ✅ Rendering ≪ training |
| NeRF baseline | `experiments/nerf/` | **heavy + long** | ❌ **Does not fit** → T2/T3 |
| Instant-NGP baseline | `experiments/instant_ngp/` | heavy | ⚠️ Uncertain → T2 |

**Roughly 70% of the engineering — the entire product layer — has no meaningful GPU
requirement.** That is what makes this project feasible on this hardware, and it happens to
be the part that makes it a product rather than a reproduction.

---

## 5. If 6 GB is not enough

In order of preference, decided at M1 with evidence:

1. **Reduce settings** — lower resolution, cap densification, fewer iterations. Costs
   visual quality; keeps everything local.
2. **Switch rasterizer** — adopt gsplat if it measurably lowers peak VRAM.
3. **Move M4 to T2 permanently** — full-quality training on Kaggle, T1 keeps a
   fast/degraded mode for development iteration. Costs the artifact round trip.
4. **T3 if granted** — removes the constraint entirely, but availability is uncertain.
5. **Paid rental** (RunPod / Vast.ai) — the escape hatch. Deferred, not rejected (ADR-005).
   The project should not *require* spending to reach its gates.

Whichever is chosen, it is written into ADR-005 **before M2 begins**.

---

## 6. Kaggle session economics

The weekly GPU quota is a real budget and must be planned like one.

| Cost | Estimate | Notes |
|---|---|---|
| Cold-start setup | TBD — M1 | Clone, deps, **compiling CUDA extensions**. Paid *every session* — no persistence |
| 3DGS training run | TBD — M1 | The actual work |
| M7 full comparison | TBD — M7 | Three baselines; NeRF dominates. **Budget before starting** |

Two consequences already established as binding (ADR-005):

- **Setup cost is measured at M1** and counted against the quota. If cold start is
  expensive, it changes how the tier is used.
- **Checkpoint/resume is mandatory** — a 12 h cap and pre-emption make any non-resumable
  run a defect.

---

## 7. What M1 must measure

Replaces every estimate above:

- [ ] Peak VRAM, T1 and T2, on the same reference scene
- [ ] Wall-clock training time, T1 and T2
- [ ] The exact T1 settings that fit in 6 GB
- [ ] gsplat vs INRIA peak VRAM at equal quality
- [ ] Viewer FPS with a real scene
- [ ] T2 cold-start setup cost against the quota
- [ ] COLMAP and ORB-SLAM3 build time and run time (ADR-004 evidence)
