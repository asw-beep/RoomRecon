# Risk Register

A living document. Update when a risk is retired, realized, or newly discovered — not only
at milestone boundaries.

Impact: **Critical** = the product does not work · **High** = a milestone is at risk ·
**Medium/Low** = degraded outcome.

---

## Architecture-killing risks

These three decide whether RoomRecon is viable. All are probed at **M1**, before anything
is built on top of them.

### R1 — 6 GB VRAM insufficient for 3DGS
**Probability:** High · **Impact:** High *(downgraded from Critical by ADR-005)*

Reference setups assume 12–24 GB. T1 has 6 GB.

*Mitigation:* validate at M1 with real measurements; reduced resolution and capped
densification; evaluate gsplat against the INRIA rasterizer.
*Fallback:* T2 (Kaggle, 16 GB) — this is why the tier strategy exists. No longer
project-ending, but it still decides where M4 lives permanently.

### R2 — Unreliable poses from handheld phone video
**Probability:** Medium · **Impact:** Critical

Monocular tracking degrades on texture-poor walls, fast motion, and low light. **Not
mitigated by the tier strategy** — SLAM is T1-only by design. This is now the single
riskiest item in the project.

*Mitigation:* a documented capture protocol; both COLMAP and ORB-SLAM3 built and measured
at M1 (ADR-004); the `PoseEstimator` interface keeps the loser swappable.
*Fallback:* whichever estimator proves more robust becomes the default. If neither is
reliable on real captures, the capture protocol or product scope changes — and that must
surface at M1, not M3.

### R3 — Browser cannot render the scene interactively
**Probability:** Medium · **Impact:** High

A `.ply` on disk is not a product. If the viewer is the bottleneck, the architecture
changes.

*Mitigation:* viewer spike at **M1**, not M5 — render a real scene and measure FPS before
committing. LOD and compression from M5 onward.
*Fallback:* aggressive compression, or a desktop viewer. Tier-independent — the viewer runs
on the user's machine.

---

## Product risks

### R4 — Bad input silently produces bad output
**Probability:** High · **Impact:** **Critical**

The worst failure mode in the project: hours of GPU time spent on a video that was never
going to reconstruct, and a user shown a broken result with no explanation.

*Mitigation:* the entire `src/capture` quality gate exists for this. Rejection happens
before any GPU time. M8 validates that the gate actually predicts real failures.
*Fallback:* reject and ask for a re-capture with a specific, actionable reason.

### R5 — Scale ambiguity
**Probability:** **Certain** · **Impact:** Medium

Monocular scale is unobservable (ADR-002). This is not a risk to be mitigated — it is a
known property to be disclosed.

*Mitigation:* `"scale": "arbitrary"` is mandatory in `camera_poses.json`; `"not metric"` is
required in the UI-facing summary. Never approximate or infer it.
*Fallback:* user-provided scale reference — deferred to v1.1.

### R6 — Large or cluttered rooms reconstruct poorly
**Probability:** Medium · **Impact:** High

*Mitigation:* keyframe and coverage optimization; capture protocol guidance.
*Fallback:* scope the demo to smaller rooms and say so plainly.

### R7 — Texture-poor scenes fail to track
**Probability:** High · **Impact:** High

Blank white walls are common in real rooms and are exactly what feature-based methods
struggle with.

*Mitigation:* feature-density metric in the capture gate; capture protocol advises
including textured regions.
*Fallback:* reject with an explanation. Documented as an operating-envelope limit at M8.

---

## Engineering risks

### R8 — Environment drift between T1 and T2
**Probability:** Medium · **Impact:** Medium · *(new with ADR-005)*

Two environments means they can diverge, producing results that differ for reasons nobody
can identify.

*Mitigation:* `scripts/verify_env.py` runs identically on both tiers and reports which one
it is on; pinned versions in the dependency inventory.

### R9 — CUDA / PyTorch / rasterizer version mismatch
**Probability:** Medium · **Impact:** High

The classic failure: a toolkit/driver/torch mismatch that only surfaces when compiling the
rasterizer extension.

*Mitigation:* pin all three together at M1 and record them in the dependency inventory.
*Fallback:* containerize the environment.

### R10 — ORB-SLAM3 build cost
**Probability:** High · **Impact:** Medium

Four transitive C++ dependencies, no native Windows path, 20+ minute builds, and it cannot
be cached on a cloud tier.

*Mitigation:* T1-only by decision (ADR-005); budget real hours at M1.
*Fallback:* COLMAP as production pose source (the ADR-004 hypothesis).

### R11 — Free-tier quota exhaustion
**Probability:** Medium · **Impact:** Medium

Kaggle's weekly quota is finite, and M7 runs three baselines including a slow NeRF.

*Mitigation:* measure cold-start cost at M1; budget M7 before starting; checkpoint across
sessions.
*Fallback:* T3 if granted; paid rental as the escape hatch (deferred, ADR-005).
**The final demo runs from local artifacts — never dependent on a free service being up.**

### R12 — Reconstruction too slow to demo
**Probability:** Medium · **Impact:** High

*Mitigation:* benchmark at M4; reduce frame counts; pre-compute demo scenes.
*Fallback:* the demo shows a pre-reconstructed scene alongside a live short capture.

### R13 — Mesh extraction quality poor
**Probability:** Medium · **Impact:** **Low**

Low impact *by design* — ADR-001 makes mesh secondary precisely so this cannot hurt.

*Mitigation:* keep it secondary; never let `gaussian/` depend on `mesh/`.
*Fallback:* point-cloud export only, with honest quality expectations shown to the user.

### R14 — NeRF baseline too slow to complete
**Probability:** High · **Impact:** **Low**

Low impact by design — `experiments/` is non-blocking (ADR-001).

*Mitigation:* T2/T3 only; budget against quota.
*Fallback:* report Instant-NGP vs 3DGS and document why NeRF was not completed. A stated
limitation is a valid result; a fabricated number is not.

---

## Retired risks

*(none yet — move risks here with the date and the evidence that retired them)*
