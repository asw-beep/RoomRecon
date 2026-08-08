# experiments/

Research code. **Quarantined from production by rule.**

```
nerf/          NeRF baseline — conceptual foundation, not a product path
instant_ngp/   Instant-NGP baseline — the acceleration question
3dgs/          3DGS through the same harness, for a fair comparison
robustness/    Pipeline behaviour across the capture corpus
```

## The one hard rule

**`src/` must never import from `experiments/`.** Not "shouldn't" — must not. If
experimental code becomes valuable enough to ship, it gets rewritten into `src/` with
tests and a gate, not promoted by import.

This exists so the project cannot collapse because a neural-field baseline was hard to
build. NeRF and Instant-NGP are explicitly non-blocking (ADR-001).

## Comparison validity

All baselines in a comparison must share: the same images, the same poses, the same
train/test split, the same metrics, and **the same compute tier**. A T1-trained 3DGS
compared against a T2-trained NeRF is not a result, it is a hardware measurement.

Budget runs against the T2 weekly quota before starting.

Tier: T2 / T3 — NeRF is impractical on 6 GB.
Milestone: M7 (comparison), M8 (robustness).
