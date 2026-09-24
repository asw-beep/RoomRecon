#!/bin/bash
# M1 gate item: prove checkpoint/resume (ADR-005 constraint 2) with a real SIGKILL.
#
# Three runs of the same config:
#   ref1, ref2  uninterrupted - their spread is the run-to-run noise (CUDA atomics
#               make gsplat non-bitwise-deterministic even with a fixed seed)
#   killed      SIGKILLed mid-interval after resume.pt reaches KILL_AFTER, then
#               relaunched with --resume and finished
# Pass: killed lands within the ref1/ref2 spread.
#
# Needs scripts/patches/gsplat-1.5.3-resume.patch applied to the gsplat clone.
# usage: [CAP=250000 STEPS=3000 EVERY=500 KILL_AFTER=1500] _wsl_resume_test.sh
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"
export CUDA_HOME=/usr/local/cuda-12.1
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="8.6"

DATA="${DATA:-$BASE/datasets/deepblending/db/drjohnson}"
CAP="${CAP:-250000}"
STEPS="${STEPS:-3000}"
EVERY="${EVERY:-500}"
KILL_AFTER="${KILL_AFTER:-1500}"
ROOT="$BASE/work/m1_resume_cap${CAP}_steps${STEPS}"
mkdir -p "$ROOT"
cd "$BASE/toolchain/gsplat"

train() {  # train <out dir> [extra args...]
  local out=$1; shift
  python examples/simple_trainer.py mcmc \
    --data_dir "$DATA" --data_factor 1 --result_dir "$out" \
    --max_steps "$STEPS" --eval_steps "$STEPS" --save_steps "$STEPS" \
    --strategy.cap-max "$CAP" --resume_every "$EVERY" \
    --disable_viewer "$@"
}

next_step() {  # prints next_step stored in resume.pt, or 0
  python -c "import torch,sys; print(torch.load(sys.argv[1], map_location='cpu', weights_only=False)['next_step'])" \
    "$1" 2>/dev/null || echo 0
}

for r in ref1 ref2; do
  echo "=== $r: uninterrupted ==="
  S=$(date +%s); train "$ROOT/$r" > "$ROOT/$r.log" 2>&1; E=$(date +%s)
  echo "$r wall $((E-S))s"
done

echo "=== killed: run until resume.pt next_step >= $KILL_AFTER, then SIGKILL ==="
K="$ROOT/killed"; rm -rf "$K"
S=$(date +%s)
train "$K" > "$ROOT/killed.part1.log" 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do
  sleep 5
  [ -f "$K/ckpts/resume.pt" ] && [ "$(next_step "$K/ckpts/resume.pt")" -ge "$KILL_AFTER" ] && break
done
# Land the kill mid-interval so some work is genuinely lost, as a pre-emption would.
sleep 15
# The trainer runs under python with dataloader workers; kill the whole group.
pkill -9 -f "result_dir $K" || true
wait $PID 2>/dev/null || true
E1=$(date +%s)
SAVED=$(next_step "$K/ckpts/resume.pt")
echo "killed at wall $((E1-S))s; resume.pt next_step=$SAVED"
ls "$K/stats" 2>/dev/null | grep -q val && echo "WARNING: run finished before the kill" || true

echo "=== killed: resume ==="
train "$K" --resume "$K/ckpts/resume.pt" > "$ROOT/killed.part2.log" 2>&1
E2=$(date +%s)
echo "resumed leg wall $((E2-E1))s; total incl. lost work $((E2-S))s"
grep "\[roomrecon\] resumed" "$ROOT/killed.part2.log"

echo "=== results (tier T1) ==="
for r in ref1 ref2 killed; do
  printf "%-7s " "$r"; cat "$ROOT/$r"/stats/val_step$(printf '%04d' $((STEPS-1))).json; echo
done
echo RESUME_TEST_DONE
