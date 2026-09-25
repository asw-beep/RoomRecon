#!/bin/bash
# Everything M1 needs from a T2 (Kaggle) session, headless. Launched by
# scripts/kaggle/m1_t2/push.sh, which generates the notebook with this repo pinned to one
# commit. Needs: GPU accelerator on, internet on.
#
# Design (docs/tier-handoff.md, docs/lessons-learned.md "T2 run 1"):
#   - Stage runner. Every stage is appended to $OUT/stages.jsonl with status, exit code and
#     wall time. A required stage failing stops the session; a best-effort one is recorded.
#   - The verdict and the package ALWAYS run, even after a failure (EXIT trap), and the
#     exit code IS the verdict. Kaggle's run status therefore means "gate passed or not".
#   - Every result is written into $OUT as it is produced, never staged in /tmp first.
#   - Idempotent. Resume state lives in $OUT too, so it is part of the session output. A
#     new session with the previous one attached as input restores it; train.py skips
#     finished runs and resumes interrupted ones (cross-session pre-emption recovery).
#   - Exactly one GPU, pinned by UUID. Kaggle's T4 accelerator is T4 x2; the second GPU
#     stays idle so timings are not contaminated by concurrent work.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOMRECON_T2_OUT:-/kaggle/working}"
SCRATCH="${ROOMRECON_T2_ROOT:-/tmp/roomrecon}"
REFS="${ROOMRECON_RESUME_REFS:-2}"      # uninterrupted references for the resume noise band
CONTINUE="${ROOMRECON_T2_CONTINUE:-0}"  # 1: push.sh --continue attached the previous output
KILL_AFTER_STEP=1500                    # SIGKILL once resume.pt holds at least this step
T0=$(date +%s)
mkdir -p "$OUT/work" "$OUT/logs"
STAGES="$OUT/stages.jsonl"; : > "$STAGES"
# What this session was asked to do, so the verdict can hold it to that.
printf '{"continue":%s,"resume_refs":%d}\n' "$([ "$CONTINUE" = 1 ] && echo true || echo false)" "$REFS" \
  > "$OUT/logs/session.json"
# Kaggle sets MPLBACKEND to the Jupyter inline backend, which our venv does not have.
export MPLBACKEND=Agg PYTHONUNBUFFERED=1 CUDA_DEVICE_ORDER=PCI_BUS_ID
export ROOMRECON_DATA="$SCRATCH/data" ROOMRECON_WORK="$OUT/work"
cd "$REPO"

# stage <name> <required|best_effort> <command...>: run it in this shell, record the outcome
stage() {
  local name=$1 kind=$2; shift 2
  local t0 rc status
  echo; echo "=== $name ($kind) ==="
  t0=$(date +%s)
  "$@"; rc=$?
  status=$([ $rc -eq 0 ] && echo ok || echo failed)
  printf '{"name":"%s","required":%s,"status":"%s","exit_code":%d,"wall_s":%d}\n' \
    "$name" "$([ "$kind" = required ] && echo true || echo false)" "$status" $rc $(( $(date +%s) - t0 )) >> "$STAGES"
  echo "--- $name: $status (exit $rc, $(( $(date +%s) - t0 ))s)"
  if [ $rc -ne 0 ] && [ "$kind" = required ]; then
    echo "required stage '$name' failed - stopping; verdict and package still run"
    exit $rc   # -> finish() via the EXIT trap
  fi
  return 0
}

# ---------------------------------------------------------------------------- stages

pin_gpu() {
  python3 scripts/gpu.py > "$OUT/logs/gpus.json" || return 1
  CUDA_VISIBLE_DEVICES=$(python3 scripts/gpu.py --pin) || return 1
  export CUDA_VISIBLE_DEVICES
  echo "$(python3 -c "import json;print(len(json.load(open('$OUT/logs/gpus.json'))))") GPU(s); pinned to $CUDA_VISIBLE_DEVICES"
}

setup() {
  bash scripts/setup_t2.sh > "$OUT/logs/setup_t2.log" 2>&1; local rc=$?
  tail -25 "$OUT/logs/setup_t2.log"
  [ $rc -eq 0 ] || return $rc
  source "$SCRATCH/venv/bin/activate"
  export CUDA_HOME=/usr/local/cuda-12.1 PATH=/usr/local/cuda-12.1/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:${LD_LIBRARY_PATH:-}
  export ROOMRECON_TOOLCHAIN="$SCRATCH/toolchain"
  export TORCH_CUDA_ARCH_LIST="$(nvidia-smi --id="$CUDA_VISIBLE_DEVICES" --query-gpu=compute_cap --format=csv,noheader)"
  pip freeze > "$OUT/logs/env_freeze.txt"   # the measured environment; source for a lock file
}

verify() {
  python scripts/verify_env.py --json > "$OUT/verify_env.json"; local rc=$?
  python - "$OUT/verify_env.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for c in d["checks"]:
    print(f"  {'PASS' if c['ok'] else ('FAIL' if c['required'] else 'n/a ')}  {c['check']:<20} {c['detail']}")
EOF
  return $rc
}

data() {
  local link="$ROOMRECON_DATA/deepblending/db/drjohnson" src
  mkdir -p "$(dirname "$link")"
  # An attached Kaggle dataset costs no GPU time to download; prefer it.
  src=$(find /kaggle/input -path '*drjohnson/sparse' -type d 2>/dev/null | head -1)
  if [ -n "$src" ]; then
    ln -sfn "$(dirname "$src")" "$link"
    python scripts/fetch_scene.py --verify "$link" --json-out "$OUT/logs/data.json"
  else
    python scripts/fetch_scene.py --dest "$ROOMRECON_DATA/deepblending" --json-out "$OUT/logs/data.json"
  fi
}

restore() {
  # Previous session's output attached as input (push.sh push --continue): bring its
  # work/ back. -n never overwrites anything this session already produced. Where Kaggle
  # mounts an attached notebook is not documented, so search for a work/ holding runs
  # rather than assume one layout.
  local prev found=()
  while IFS= read -r prev; do
    compgen -G "$prev/*/run.json" >/dev/null || continue
    cp -rn "$prev/." "$OUT/work/" && found+=("$prev") && echo "restored $prev"
  done < <(find /kaggle/input -maxdepth 6 -type d -name work 2>/dev/null)
  python3 - "$OUT/logs/restore.json" "${found[@]}" <<'EOF'
import json, sys
from pathlib import Path
out, sources = sys.argv[1], sys.argv[2:]
runs = sorted({p.parent.name for s in sources for p in Path(s).glob("*/run.json")})
json.dump({"restored_from": sources, "runs": runs}, open(out, "w"), indent=1)
print(f"{len(runs)} run(s) restored: {runs}" if runs else "no previous session attached - fresh start")
EOF
  # Asked to continue but found nothing: stop before a fresh start re-spends the GPU time.
  [ "$CONTINUE" != 1 ] || [ ${#found[@]} -gt 0 ]
}

baseline() { python scripts/train.py --config configs/m1_drjohnson.yaml; }

references() {
  local i
  for i in $(seq 1 "$REFS"); do
    python scripts/train.py --config configs/m1_resume_check.yaml \
      --result-dir "$OUT/work/m1_resume_ref_$i" || return 1
  done
}

resume_check() {
  local R="$OUT/work/m1_resume_check" pid pgid seen="" m
  if python3 - "$R/run.json" <<'EOF'
import json, sys
try:
    legs = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if legs and legs[-1].get("status") == "completed" and legs[-1].get("resumed_from") else 1)
EOF
  then echo "resume check already completed in a previous session"; return 0; fi
  rm -rf "$R"   # a partial earlier attempt would trip the kill early

  # Leg 1 in its own process group, so one SIGKILL takes the launcher and the trainer
  # together - as a pre-emption does.
  # setsid does not fork here (a background job is not a group leader), so the new
  # group's id is the pid. Never read it from ps right after the spawn: before setsid()
  # runs, that is still OUR group, and killing it would kill this session.
  setsid python scripts/train.py --config configs/m1_resume_check.yaml &
  pid=$!; pgid=$pid
  kill_group() {
    [ "$(ps -o pgid= "$pid" 2>/dev/null | tr -d ' ')" = "$pgid" ] \
      || { echo "leg 1 is not leading its own process group - refusing to kill"; return 1; }
    kill -9 -- "-$pgid"; wait "$pid" 2>/dev/null; return 0
  }
  local deadline=$(( $(date +%s) + 1800 ))
  while :; do
    kill -0 "$pid" 2>/dev/null || { echo "leg 1 exited before the kill point"; return 1; }
    [ "$(date +%s)" -lt "$deadline" ] || { echo "no resume.pt at step >= $KILL_AFTER_STEP within 30 min"; kill_group; return 1; }
    m=$(stat -c %Y "$R/ckpts/resume.pt" 2>/dev/null || true)
    # resume.pt is renamed into place atomically; load it only when it changes
    if [ -n "$m" ] && [ "$m" != "$seen" ]; then
      seen=$m
      python -c "import torch,sys; sys.exit(torch.load(sys.argv[1],map_location='cpu',weights_only=False)['next_step'] < $KILL_AFTER_STEP)" \
        "$R/ckpts/resume.pt" 2>/dev/null && break
    fi
    sleep 2
  done
  sleep 15   # land mid-interval so work is genuinely lost, as in a pre-emption
  kill_group || return 1
  echo "leg 1 SIGKILLed (process group $pgid)"
  [ -f "$R/ckpts/resume.pt" ] || { echo "no resume.pt after the kill"; return 1; }
  python scripts/train.py --config configs/m1_resume_check.yaml   # leg 2: must resume
}

# ---------------------------------------------------------------------------- finish

finish() {
  trap - EXIT
  echo; echo "=== verdict ==="
  python3 scripts/t2_verdict.py --out "$OUT"; local verdict=$?
  echo "=== package ==="
  # Results only; resume.pt / ckpt_*.pt stay in $OUT/work for cross-session resume but
  # are training state, not part of the download artifact.
  (cd "$OUT" && tar czf m1_t2_artifact.tar.gz --ignore-failed-read \
     verdict.json stages.jsonl verify_env.json logs \
     $(cd "$OUT" && ls -d work/*/run.json work/*/stats work/*/cfg.yml work/m1_drjohnson/ply 2>/dev/null)) \
    && ls -lh "$OUT/m1_t2_artifact.tar.gz"
  echo "=== T2 session total $(( $(date +%s) - T0 ))s ==="
  # A stage failure already fails the verdict; the verdict decides the exit code.
  exit $verdict
}
trap finish EXIT

stage "pin gpu"      required    pin_gpu
stage "setup"        required    setup
stage "verify env"   required    verify
stage "data"         required    data
stage "restore"      "$([ "$CONTINUE" = 1 ] && echo required || echo best_effort)" restore
stage "baseline"     required    baseline
stage "references"   required    references
stage "resume check" required    resume_check
