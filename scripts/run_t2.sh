#!/bin/bash
# Everything M1 needs from a T2 (Kaggle) session, headless. The notebook is two lines:
#
#   !rm -rf RoomRecon && git clone --depth 1 https://github.com/asw-beep/RoomRecon.git
#   !bash RoomRecon/scripts/run_t2.sh
#
# The rm makes a rerun in the same session pick up the latest push instead of a stale clone.
#
# Needs: GPU accelerator on, internet on, the drjohnson dataset attached as input.
# Produces /kaggle/working/m1_t2_artifact.tar.gz - the download artifact (see
# docs/tier-handoff.md). Every phase prints its wall time.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT=/kaggle/working
T0=$(date +%s)
# Kaggle sets MPLBACKEND to the Jupyter inline backend, which our venv does not have;
# matplotlib (pulled in by torchmetrics) then fails on import. We are headless anyway.
export MPLBACKEND=Agg

echo "=== 1/4 setup ==="
bash "$REPO/scripts/setup_t2.sh" 2>&1 | tee "$OUT/setup_t2.log"
source /tmp/roomrecon/venv/bin/activate
export CUDA_HOME=/usr/local/cuda-12.1 PATH=/usr/local/cuda-12.1/bin:$PATH
export ROOMRECON_TOOLCHAIN=/tmp/roomrecon/toolchain
export TORCH_CUDA_ARCH_LIST="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)"
python "$REPO/scripts/verify_env.py" --json > "$OUT/verify_env.json"

# Kaggle mounts datasets read-only under /kaggle/input/<slug>/; link it into the
# layout the configs expect instead of copying 200 MB.
SCENE=$(dirname "$(find /kaggle/input -path '*drjohnson/sparse' -type d | head -1)")
[ -d "$SCENE/images" ] || { echo "drjohnson dataset not attached"; exit 1; }
mkdir -p /tmp/data/deepblending/db
ln -sfn "$SCENE" /tmp/data/deepblending/db/drjohnson
export ROOMRECON_DATA=/tmp/data ROOMRECON_WORK=$OUT/work
cd "$REPO"

echo "=== 2/4 baseline: same config as T1, uninterrupted ==="
python scripts/train.py --config configs/m1_drjohnson.yaml

echo "=== 3/4 resume check: SIGKILL mid-run, then the same command again ==="
rm -rf "$OUT/work/m1_resume_check"   # a stale resume.pt would trip the kill early
python scripts/train.py --config configs/m1_resume_check.yaml &
RC=$OUT/work/m1_resume_check/ckpts/resume.pt
for _ in $(seq 900); do
  [ -f "$RC" ] && python -c "import torch,sys; sys.exit(torch.load('$RC',map_location='cpu',weights_only=False)['next_step'] < 1500)" 2>/dev/null && break
  sleep 2
done
sleep 15   # land mid-interval so work is genuinely lost, as in a pre-emption
pkill -9 -f "configs/m1_resume_check.yaml" || true
pkill -9 -f "result_dir $OUT/work/m1_resume_check" || true
wait || true
python scripts/train.py --config configs/m1_resume_check.yaml

echo "=== 4/4 package download artifact ==="
# resume.pt / ckpt_*.pt are training state, not results - they stay behind.
cd "$OUT"
tar czf m1_t2_artifact.tar.gz setup_t2.log verify_env.json \
  work/m1_drjohnson/{ply,stats,run.json,cfg.yml} \
  work/m1_resume_check/{stats,run.json}
ls -lh m1_t2_artifact.tar.gz
echo "=== T2 session total $(( $(date +%s) - T0 ))s ==="
