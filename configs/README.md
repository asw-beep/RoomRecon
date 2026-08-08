# configs/

Configuration is part of the reproducibility contract. Same input + same config + same
pipeline version → reproducible result.

## Rules

- **Configs are versioned and committed.** A result whose config was not recorded is not a
  result.
- **The pipeline version is stamped into every artifact**, so a scene can always be traced
  back to what produced it.
- **Seeds are explicit.** Never rely on a default.
- **Validated on startup.** A malformed config fails immediately with a clear message, not
  three hours into a training run.

## Planned

| File | Purpose | Milestone |
|---|---|---|
| `t1_6gb.yaml` | Laptop / WSL2 budget: downscaled images, capped densification | M1 |
| `t2_16gb.yaml` | Kaggle budget: full settings | M1 |
| `capture.yaml` | Quality thresholds and rejection rules | M2 |

The tier configs share a code path. They differ in budget only — never in behaviour.
