# Architecture Decision Records

Each ADR records one decision, why it was made, what it costs, and what was rejected.
**Decisions are changed by writing a new ADR, not by editing an accepted one.**

| # | Decision | Status |
|---|---|---|
| [001](001-3dgs-primary-representation.md) | 3D Gaussian Splatting as the primary scene representation | Accepted |
| [002](002-monocular-rgb-input.md) | Monocular RGB video as the only input | Accepted |
| [003](003-modular-monolith.md) | Modular monolith, SQLite, local job worker | Accepted |
| [004](004-pose-source.md) | Production pose source: COLMAP vs ORB-SLAM3 | 🔶 Deferred to M1 evidence |
| [005](005-compute-strategy.md) | Three-tier compute: WSL2 laptop / Kaggle / campus | Accepted |
| [007](007-kaggle-primary-compute.md) | Kaggle as the primary compute tier, laptop for interaction (amends 005) | 🔶 Proposed, G1 review |
| [008](008-optional-phone-depth.md) | Phone depth as an optional input, RGB-only fallback (amends 002, 006) | 🔶 Proposed, G1 review |

## Format

Context → Decision → Consequences (positive, negative, neutral) → Alternatives considered.

Two standards apply throughout:

- **Record what a decision costs**, not only what it buys. An ADR with no negative
  consequences has not been thought through.
- **Never fabricate a number.** Unmeasured values are `TBD — <milestone>`. Figures from
  the source papers came from their hardware and are never restated as ours.
