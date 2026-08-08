# scripts/

Operational entry points. Every heavy stage must be reachable from here without a notebook
or a human clicking through steps (ADR-005 constraint 3).

## Planned

| Script | Purpose | Milestone |
|---|---|---|
| `verify_env.py` | Dependency pass/fail table; identifies which tier it is running on | M1 |
| `setup_t2.sh` | Cold-start a Kaggle session: clone → deps → build CUDA extensions | M1 |
| `run_pipeline.py` | Full video → scene, headless, config-driven | M4 |

## The standard

A T2 session must reduce to:

```
git clone <repo> && bash scripts/setup_t2.sh && python scripts/run_pipeline.py --config configs/t2_16gb.yaml
```

No interactive-only steps. No manual cell ordering. If a stage cannot be run this way, it
is not finished.
