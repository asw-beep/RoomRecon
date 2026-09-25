#!/bin/bash
# M1 MuSHRoom, part 2 of 2, on a T2 GPU session: train and evaluate every room x pose
# source (device, sfm) x variant (baseline, indoor). Needs part 1's output attached
# (scripts/kaggle/m1_mushroom_train/job.env). Launched by:
#   bash scripts/kaggle/push.sh m1_mushroom_train push [--continue]
#
# Same contract as run_t2.sh. One difference: each training run is a best-effort stage,
# so one crashing run does not cost the others; the verdict holds every run to account.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOMRECON_T2_OUT:-/kaggle/working}"
SCRATCH="${ROOMRECON_T2_ROOT:-/tmp/roomrecon}"
ROOMS="${MUSHROOM_ROOMS:-koivu vr_room}"
CONTINUE="${ROOMRECON_T2_CONTINUE:-0}"
KEEP_RENDERS=4        # per test set, final step: enough to look at, not thousands of files
T0=$(date +%s)
mkdir -p "$OUT/work" "$OUT/logs/prep"
STAGES="$OUT/stages.jsonl"; : > "$STAGES"
printf '{"continue":%s,"rooms":"%s"}\n' "$([ "$CONTINUE" = 1 ] && echo true || echo false)" "$ROOMS" \
  > "$OUT/logs/session.json"
export MPLBACKEND=Agg PYTHONUNBUFFERED=1 CUDA_DEVICE_ORDER=PCI_BUS_ID
export ROOMRECON_DATA="$SCRATCH/data" ROOMRECON_WORK="$OUT/work"
cd "$REPO"
# shellcheck source=t2_stages.sh
source scripts/t2_stages.sh

data() {
  local prep room arm
  prep=$(find_input "/rooms")
  [ -n "$prep" ] || { echo "part 1 output (rooms/) not attached - push m1_mushroom_prep first"; return 1; }
  mkdir -p "$ROOMRECON_DATA/mushroom"
  for room in $ROOMS; do
    [ -f "$prep/mushroom_$room.tar" ] || { echo "$prep/mushroom_$room.tar missing"; return 1; }
    tar xf "$prep/mushroom_$room.tar" -C "$ROOMRECON_DATA/mushroom" || return 1
    cp "$prep/$room.prep_report.json" "$OUT/logs/prep/"
    for arm in device sfm; do
      ln -sfn ../images "$ROOMRECON_DATA/mushroom/$room/$arm/images"
      [ -f "$ROOMRECON_DATA/mushroom/$room/$arm/sparse/0/images.bin" ] || { echo "$room/$arm: no sparse model"; return 1; }
    done
    echo "$room: $(ls "$ROOMRECON_DATA/mushroom/$room/images" | wc -l) images"
  done
}

# tidy <result dir>: after a COMPLETED run only. Training state is not a result.
tidy() {
  local d=$1 set
  rm -rf "$d/ckpts" "$d/tb" "$d/videos"
  for set in val xseq; do
    ls "$d/renders/${set}_step14999_"*.png 2>/dev/null | sort | tail -n +$((KEEP_RENDERS + 1)) | xargs -r rm -f
  done
  find "$d/renders" -name '*.png' ! -name '*_step14999_*' -delete 2>/dev/null
  return 0
}

# train_one <room> <arm> <variant>
train_one() {
  local room=$1 arm=$2 variant=$3 d split
  d="$OUT/work/mushroom_${room}_${arm}_${variant}"
  split="$ROOMRECON_DATA/mushroom/$room/$arm/split.json"
  # A missing or unreadable split is a broken data stage, NOT "nothing to evaluate".
  python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$split" || { echo "unreadable $split"; return 1; }
  if ! python3 -c "import json,sys; s=json.load(open(sys.argv[1])); sys.exit(0 if s['val'] and s['xseq'] else 1)" "$split"; then
    mkdir -p "$d"
    echo '{"reason": "no test view registered by both pose sources"}' > "$d/skipped.json"
    echo "skipped: no common test views"; return 0
  fi
  MUSHROOM_ROOM=$room MUSHROOM_ARM=$arm python scripts/train.py --config "configs/m1_mushroom_${variant}.yaml" \
    || return 1
  tidy "$d"
}

finish() {
  trap - EXIT
  echo; echo "=== verdict ==="
  # shellcheck disable=SC2086
  python3 scripts/mushroom_verdict.py train --out "$OUT" --rooms $ROOMS; local verdict=$?
  echo "=== package ==="
  # Results only. The scenes (ply/) stay in the session output: fetch them one at a time.
  (cd "$OUT" && tar czf m1_mushroom_artifact.tar.gz --ignore-failed-read \
     verdict.json stages.jsonl verify_env.json logs \
     $(ls -d work/*/run.json work/*/cfg.yml work/*/stats work/*/renders work/*/skipped.json 2>/dev/null)) \
    && ls -lh "$OUT/m1_mushroom_artifact.tar.gz"
  echo "=== T2 session total $(( $(date +%s) - T0 ))s ==="
  exit $verdict
}
trap finish EXIT

stage "pin gpu"    required pin_gpu
stage "setup"      required setup
stage "verify env" required verify
stage "data"       required data
stage "restore"    "$([ "$CONTINUE" = 1 ] && echo required || echo best_effort)" restore_work
# Baselines first: if the session is cut short, the pose-source comparison is what survives.
for variant in baseline indoor; do
  for room in $ROOMS; do
    for arm in device sfm; do
      stage "train $room $arm $variant" best_effort train_one "$room" "$arm" "$variant"
    done
  done
done
