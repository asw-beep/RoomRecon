# M1 on T2 (Kaggle): headless, from the repo

Runs `scripts/run_t2.sh` on a Kaggle GPU: the same `train.py` and configs as T1, so the two
tiers can be compared, as the G1 gate requires. Nothing is interactive: push, wait, fetch.
Locally you only need the small Kaggle CLI. The full procedure and design are in
`docs/tier-handoff.md`. Why it works this way: `docs/lessons-learned.md` §7 (T2 run 1).

There is **no notebook to edit**. `push.sh` generates it for each push: one cell that
clones this repo at the commit being pushed and runs `run_t2.sh`. All logic lives in
the repo, under test.

## One-time setup (Windows, Git Bash)

1. **Kaggle account:** in Settings, verify your phone (required for GPU and internet),
   check your weekly GPU quota, and note your username (the end of `kaggle.com/<username>`).
2. **CLI:** `python -m pip install --no-cache-dir kaggle`. If `kaggle` isn't found on
   PATH, that's fine: `push.sh` calls it through `python`.
3. **Sign in:** `bash push.sh login`, or save an API token as `C:\Users\ASWIN\.kaggle\access_token`.
   Never put tokens in the repo.
4. **Username:** `echo 'export KAGGLE_USERNAME=<name>' >> ~/.bashrc && source ~/.bashrc`
5. **Check:** `bash push.sh check`
6. **Optional, saves GPU quota:** upload drjohnson as a private Kaggle dataset
   (`docs/tier-handoff.md`, "T1 → T2") and `export KAGGLE_DATASET=<owner>/<slug>`. Without it,
   each session downloads the scene from the pinned mirror revision.

## Each run

```bash
bash push.sh push              # refuses a dirty tree, an unpushed commit, or failing tests
bash push.sh status            # queued / running / complete / error
bash push.sh fetch             # results only -> ./output/, validated, verdict printed
bash push.sh push --continue   # after a pre-emption: resumes from the previous version's output
```

**Status means the gate verdict.** `complete` means every gate check passed. `error` means
one did not, or a required stage failed. Either way, `fetch` gets `verdict.json`, which
says which check failed and why.

## What lands where

| What | Where | Size |
|---|---|---|
| Kaggle CLI | C:, in the existing Python | a few MB |
| Sign-in token | `C:\Users\ASWIN\.kaggle\` | bytes |
| Fetched results | `./output/` on **E:**, git-ignored, replaced on every fetch | the baseline PLY is the bulk |
| Environment, data, resume checkpoints | the Kaggle session only | 0 locally |

## Details

- **GPU:** Kaggle's T4 accelerator is **T4 ×2**. The job is pinned to one GPU by UUID and
  the other stays idle. `run.json` records both. Tier label: "T2 (Kaggle, T4 ×2, 1 used)".
- **Setup time counts against the GPU quota.** `stages.jsonl` times it; it is the M1
  "T2 cold-start setup cost". `logs/env_freeze.txt` records the exact environment, and the
  first passing run's freeze becomes the lock file.
- **Not yet exercised on Kaggle:** this path end to end, and `--continue` in particular.
  The first run is the real test.
