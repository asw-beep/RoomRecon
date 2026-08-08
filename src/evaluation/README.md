# src/evaluation

**Responsibility:** measure what the system actually does, so no claim in this project is
unsupported.

Owns held-out view metrics (PSNR, SSIM, LPIPS), timing and resource accounting, and the
robustness harness that runs the pipeline across the capture corpus — good, blurry,
low-light, fast-motion, low-coverage, no-loop, texture-poor.

Two standing rules:

- **Never invent a number.** Every metric is `TBD — <milestone>` until measured on real
  hardware. Figures from papers are never restated as ours.
- **Every measurement carries its tier.** T1 and T2 numbers are not comparable and must
  never be presented as if they were.

The most valuable output of this module is not a good score. It is a precise statement of
when RoomRecon fails — and evidence that the M2 capture-quality gate predicts those
failures before the GPU time is spent.

Inputs: reconstructions + ground-truth held-out views.
Outputs: metrics files, comparison tables, `docs/evaluation/robustness.md`.

Milestones: M4 (first metrics), M7 (comparison), M8 (robustness).
