#!/bin/bash
# 3DGS training on T1 (RTX 3050, 6GB / ~4.7GB usable after the desktop baseline).
#
# MCMC strategy is deliberate: --strategy.cap-max is a HARD ceiling on Gaussian count,
# which bounds VRAM. The default densification heuristic grows adaptively and can
# overrun 6GB unpredictably.
#
# usage: DATA=<colmap dir> CAP=<n> STEPS=<n> TAG=<name> _wsl_train_3dgs.sh
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"
export CUDA_HOME=/usr/local/cuda-12.1
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="8.6"

DATA="${DATA:-$BASE/datasets/deepblending/db/drjohnson}"
CAP="${CAP:-1000000}"
STEPS="${STEPS:-15000}"
TAG="${TAG:-drjohnson}"
OUT="$BASE/work/${TAG}_cap${CAP}_steps${STEPS}"
mkdir -p "$OUT"

nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 2 > "$OUT/vram_samples.txt" &
SMI_PID=$!
trap "kill $SMI_PID 2>/dev/null || true" EXIT

cd "$BASE/toolchain/gsplat"
echo "=== 3DGS: $TAG cap_max=$CAP steps=$STEPS data=$DATA ==="
START=$(date +%s)
python examples/simple_trainer.py mcmc \
  --data_dir "$DATA" \
  --data_factor 1 \
  --result_dir "$OUT" \
  --max_steps "$STEPS" \
  --strategy.cap-max "$CAP" \
  --save_ply \
  --disable_viewer 2>&1 | tail -12
END=$(date +%s)

kill $SMI_PID 2>/dev/null || true
echo "=== wall clock: $((END-START))s ==="
echo "=== peak GPU MiB (incl desktop baseline) ==="; sort -n "$OUT/vram_samples.txt" | tail -1
echo "=== idle baseline MiB ==="; sort -n "$OUT/vram_samples.txt" | head -1
echo "=== eval stats ==="; cat "$OUT"/stats/val*.json 2>/dev/null; echo
echo "=== outputs ==="; ls -lh "$OUT"/ply/ 2>/dev/null; du -sh "$OUT"
echo TRAIN_DONE
