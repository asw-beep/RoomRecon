# Dependency Inventory

Every external dependency: what it does, which tier it runs on, whether it needs CUDA, and
whether it builds on Windows.

**Versions marked `TBD — M1` are pinned during M1 installation.** Nothing is pinned by
guessing; a version recorded here without having been installed would be a fabrication.

Verified environment (2026-08-08): RTX 3050 Laptop 6 GB, driver 581.86 · Python 3.12.10
(WindowsApps stub) · Node 25.6.1 · ffmpeg present · WSL2 Ubuntu-22.04 (stopped) · Docker
Desktop (installed, daemon stopped) · **missing: cmake, conda, COLMAP, CUDA toolkit**.

---

## Reconstruction core

| Dependency | Purpose | Version | Tier | CUDA | Native Windows | Notes |
|---|---|---|---|---|---|---|
| **COLMAP** | SfM poses + sparse points | TBD — M1 | T1 | Optional (feature matching) | ✅ Yes | Candidate production pose source (ADR-004). 3DGS consumes its output natively |
| **ORB-SLAM3** | Visual SLAM, keyframes, loop closure | TBD — M1 | **T1 only** | No | ❌ No | Needs Pangolin, DBoW2, g2o, Eigen, OpenCV. 20+ min build → never rebuilt on T2 (ADR-005) |
| **3DGS** (INRIA reference) | Gaussian training + rasterizer | TBD — M1 | T1 / T2 | **Required** | ⚠️ Painful | Baseline implementation |
| **gsplat** (nerfstudio) | Alternative Gaussian rasterizer | TBD — M1 | T1 / T2 | **Required** | ⚠️ Fiddly | **Evaluate against INRIA at M1** — reported more memory-efficient, which matters disproportionately at 6 GB |
| **PyTorch** | Training runtime | TBD — M1 | T1 / T2 | **Required** | ✅ Yes | Must match the installed CUDA toolkit |
| **CUDA Toolkit** | Compiling rasterizer extensions | TBD — M1 | T1 / T2 | — | ✅ Yes | Must be compatible with driver 581.86 |
| **OpenCV** | Frame ops, feature detection, blur metrics | TBD — M1 | T1 | No | ✅ Yes | Used by both `capture/` and `tracking/` |
| **ffmpeg** | Video probing and frame extraction | installed | T1 | No | ✅ Yes | Already present |

## Build toolchain

| Dependency | Purpose | Version | Tier | Status |
|---|---|---|---|---|
| **cmake** | Building COLMAP / ORB-SLAM3 | TBD — M1 | T1 | ❌ Not installed |
| **conda or uv** | Python environment pinning | TBD — M1 | T1 / T2 | ❌ Not installed |
| **Python** | 3.10 or 3.11 | TBD — M1 | T1 / T2 | ⚠️ Only the 3.12 WindowsApps stub — **not viable** for the 3DGS ecosystem |
| **WSL2 Ubuntu-22.04** | Linux build environment | installed | T1 | ⚠️ Stopped; GPU passthrough unverified |
| **Docker Desktop** | Optional containerized builds | installed | T1 | ⚠️ Daemon stopped |

## Backend

| Dependency | Purpose | Version | Tier | Notes |
|---|---|---|---|---|
| **FastAPI** | HTTP API | TBD — M5 | T1 | Frozen API surface in `src/api/README.md` |
| **uvicorn** | ASGI server | TBD — M5 | T1 | |
| **SQLite** | Project metadata | stdlib | T1 | Via Python stdlib; no server (ADR-003) |
| **pydantic** | Config + schema validation | TBD — M5 | T1 | Enforces `docs/data-contracts.md` |
| **pytest** | Test runner | TBD — M2 | T1 / T2 | GPU tests marked for deselection |

## Frontend

| Dependency | Purpose | Version | Tier | Notes |
|---|---|---|---|---|
| **React** | UI | TBD — M5 | browser | |
| **Three.js** | 3D rendering | TBD — M5 | browser | |
| **React Three Fiber** | React ↔ Three binding | TBD — M5 | browser | |
| **splat renderer** | Gaussian rendering in-browser | TBD — M1 spike | browser | **Selected at the M1 viewer spike** — Risk #3 is architecture-killing, so this is probed early, not at M5 |
| **Vite** | Build tooling | TBD — M5 | browser | |
| **Node** | 25.6.1 | installed | T1 | |

## Experiments — `experiments/`, T2/T3 only

| Dependency | Purpose | Version | Notes |
|---|---|---|---|
| **NeRF** (reference impl.) | M7 baseline | TBD — M7 | Impractical on 6 GB. Non-blocking (ADR-001) |
| **Instant-NGP** | M7 baseline | TBD — M7 | Fully fused CUDA; build cost is the main risk |
| **LPIPS** | Perceptual metric | TBD — M7 | Alongside PSNR/SSIM |

---

## Risk notes

**The three that will cost the most time**, in order:

1. **ORB-SLAM3 build.** Four transitive C++ dependencies, no Windows path, and it cannot
   be cached on a cloud tier. Budget real hours for this at M1.
2. **CUDA / PyTorch / rasterizer version alignment.** The classic failure mode — a
   toolkit/driver/torch mismatch that only surfaces when compiling the rasterizer
   extension. Pin all three together and record them here.
3. **Environment drift between T1 and T2** (Risk #4). `scripts/verify_env.py` must run
   identically on both tiers and report which one it is on.

## Licensing

To be completed at M1 alongside installation. Note in particular that the **INRIA 3DGS
reference implementation is released under a non-commercial research license** — relevant
if this project is ever positioned beyond coursework. gsplat's licensing differs and is
part of why it is being evaluated.
