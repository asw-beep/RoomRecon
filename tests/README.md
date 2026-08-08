# tests/

Tests are gate evidence, not a formality. A milestone does not close because the happy
path runs.

## What every stage must test

- **The failure path.** Bad input rejected with the *correct* reason — not just rejected.
  "Bad input silently produces bad output" is the highest-impact risk in the register.
- **Determinism.** Same input + same config + same seed → identical output. Especially
  `src/preprocessing`, from which everything downstream inherits reproducibility.
- **Schema conformance.** Artifacts crossing a module or tier boundary match
  `docs/data-contracts.md`.

## Layout

Mirror `src/`. Fixtures live in `tests/fixtures/` and must be small enough to commit —
short clips and tiny image sets, never full room captures.

Tests must run on both tiers. Anything requiring a GPU is marked so it can be deselected
on a machine without one.
