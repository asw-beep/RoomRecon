# Tier Handoff: T1 ⇄ T2

How work moves between the laptop (T1) and Kaggle (T2). Only schema-conforming artifacts
cross the boundary (ADR-005); code crosses by `git clone`, never by upload.

> **Status:** procedure written, **not yet executed.** The M1 gate needs one full round
> trip. Measured sizes and times get filled in from that run, not before.

## What crosses

| Direction | Artifact | Contents | Size |
|---|---|---|---|
| T1 → T2 | scene dataset (Kaggle dataset) | `images/` + COLMAP `sparse/0/` | 198 MiB for drjohnson (measured) |
| T2 → T1 | `m1_t2_artifact.tar.gz` | `verdict.json`, `stages.jsonl`, `verify_env.json`, `logs/` (setup, GPU inventory, `pip freeze`, data fingerprint), and per run `run.json` + `stats/` + `cfg.yml`; trained `.ply` of the baseline | TBD — first run of this path |

Poses are computed on T1 only (ADR-005 constraint 1), so the upload is always
frames + poses + sparse, never raw video. Training state (`resume.pt`, `ckpt_*.pt`) does
not cross. It stays in the Kaggle session output, only for resuming on T2.

Every `run.json` carries `tier`, `pipeline_version`, `config_hash` and `hardware` taken
from the machine, which is what makes a T1-vs-T2 comparison honest.

## T1 → T2

1. Package the scene from WSL (writes `E:\roomrecon-t2\drjohnson.zip`):
   ```bash
   cd ~/roomrecon/datasets/deepblending/db && python3 -m zipfile -c /mnt/e/roomrecon-t2/drjohnson.zip drjohnson
   ```
2. kaggle.com → Datasets → New Dataset → upload the zip, keep it private.
   Any slug works; `run_t2.sh` finds the scene by its `drjohnson/sparse` folder.
3. Push the code: `git push origin main`. T2 clones from GitHub.

## On T2

Never build the notebook by hand. From the repo, with the commit pushed to GitHub:

```bash
cd scripts/kaggle/m1_t2
KAGGLE_DATASET=<owner>/<slug> bash push.sh push   # KAGGLE_DATASET optional, see below
```

`push.sh` refuses to push a dirty tree, a commit that is not on GitHub, or failing unit
tests. It generates a one-cell notebook that clones **that exact commit** and runs
`scripts/run_t2.sh` headless, on Kaggle's T4 accelerator. Without `KAGGLE_DATASET`, the
scene is downloaded in-session from the pinned mirror revision. That works, but it costs
GPU time.

`run_t2.sh` runs these stages, each recorded in `stages.jsonl`:
pin GPU → setup → `verify_env.py` → data (fingerprinted) → restore → baseline
`configs/m1_drjohnson.yaml` (the same file T1 runs) → 2 uninterrupted resume references →
SIGKILL/resume check. Then it **always** writes `verdict.json` and the artifact. Its exit
code is the verdict, so Kaggle's status means "gate passed or not".

**One GPU, pinned by UUID.** Kaggle's T4 accelerator is **T4 ×2**. The job uses one GPU;
the other stays idle, so timings are not shared with concurrent work. `run.json` records
both GPUs and the one used. Report the tier as "T2 (Kaggle, T4 ×2, 1 used)".

**If the session dies (pre-emption, 12 h limit):** `bash push.sh push --continue`. The new
version gets the previous version's output as input. `run_t2.sh` restores its `work/`:
finished runs are skipped (`train.py` is idempotent) and the interrupted one resumes from
its `resume.pt`. *(Implemented, not yet exercised on Kaggle.)*

## T2 → T1

1. `bash push.sh fetch` downloads only the results (`verdict.json`, `stages.jsonl`, the
   artifact, logs) into `scripts/kaggle/m1_t2/output/`. Resume checkpoints stay on Kaggle.
   The fetch fails loudly on an empty or missing file and prints the verdict.
2. Unpack and view the T2-trained scene in the T1 browser viewer:
   ```bash
   mkdir -p ~/roomrecon/work/from_t2 && tar xzf "/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/scripts/kaggle/m1_t2/output/m1_t2_artifact.tar.gz" -C ~/roomrecon/work/from_t2
   ```
3. Record the T2 numbers in `docs/m1-downloads.csv`, each with its tier.

The round trip is done when a scene trained on T2 renders in the browser on T1.
