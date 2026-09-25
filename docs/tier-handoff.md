# Tier Handoff: T1 ⇄ T2

How work moves between the laptop (T1) and Kaggle (T2). Only schema-conforming artifacts
cross the boundary (ADR-005); code crosses by `git clone`, never by upload.

> **Status:** procedure written, **not yet executed.** The M1 gate needs one full round
> trip. Measured sizes and times get filled in from that run, not before.

## What crosses

| Direction | Artifact | Contents | Size |
|---|---|---|---|
| T1 → T2 | scene dataset (Kaggle dataset) | `images/` + COLMAP `sparse/0/` | 198 MiB for drjohnson (measured) |
| T2 → T1 | `m1_t2_artifact.tar.gz` | trained `.ply`, `stats/`, `run.json`, `cfg.yml`, `verify_env.json`, `setup_t2.log` | TBD — first T2 run |

Poses are computed on T1 only (ADR-005 constraint 1), so the upload is always
frames + poses + sparse, never raw video. Training state (`resume.pt`, `ckpt_*.pt`) does
not cross; it is only for resuming on the same tier.

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

New notebook → Settings: **Accelerator GPU T4 ×2**, **Internet on** → Add Input → the
dataset. One cell:

```bash
!rm -rf RoomRecon && git clone --depth 1 https://github.com/asw-beep/RoomRecon.git
!bash RoomRecon/scripts/run_t2.sh
```

Then **Save Version → Save & Run All (Commit)** so it runs headless with no browser
attached. `run_t2.sh` does: setup (timed per phase) → `verify_env.py` → baseline
`configs/m1_drjohnson.yaml` (the same file T1 ran) → SIGKILL/resume check → package the
download artifact.

**If the session dies mid-baseline:** in a new version, add the previous version's output
as an input, copy its `work/` into `/kaggle/working/`, and rerun. `train.py` finds
`resume.pt` and continues. *(Cross-session resume is the documented path but has not
been exercised; the in-session SIGKILL check is what the gate demonstrates.)*

## T2 → T1

1. Notebook → Output → download `m1_t2_artifact.tar.gz` to `E:\roomrecon-t2\`.
2. Unpack and view the T2-trained scene in the T1 browser viewer:
   ```bash
   mkdir -p ~/roomrecon/work/from_t2 && tar xzf /mnt/e/roomrecon-t2/m1_t2_artifact.tar.gz -C ~/roomrecon/work/from_t2
   ```
3. Record the T2 numbers in `docs/m1-downloads.csv`, each with its tier.

The round trip is done when a scene trained on T2 renders in the browser on T1.
