#!/bin/bash
# scratch - reverts the accidental torch upgrade.
# torchmetrics[image] pulled torch 2.14.0+cu130, replacing the verified 2.5.1+cu121 build
# and breaking CUDA-extension compilation against our CUDA 12.1 nvcc.
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"

echo "=== removing CUDA 13 packages ==="
pip uninstall -y torch torchvision triton \
  nvidia-cublas nvidia-cuda-cupti nvidia-cuda-nvrtc nvidia-cuda-runtime \
  nvidia-cudnn-cu13 nvidia-cufft nvidia-cufile nvidia-curand nvidia-cusolver \
  nvidia-cusparse nvidia-cusparselt-cu13 nvidia-nccl-cu13 nvidia-nvjitlink \
  nvidia-nvshmem-cu13 nvidia-nvtx cuda-toolkit cuda-bindings cuda-pathfinder \
  2>&1 | grep -cE 'Successfully uninstalled|not installed' || true

echo "=== reinstalling verified torch 2.5.1+cu121 ==="
pip install torch==2.5.1+cu121 torchvision==0.20.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -4

echo "=== pinning torch so nothing upgrades it again ==="
cat > "$BASE/constraints.txt" <<'EOF'
# Pin the CUDA-12.1-matched torch stack. Anything that tries to pull a different torch
# (e.g. torchmetrics[image]) must be installed with -c this file.
torch==2.5.1+cu121
torchvision==0.20.1+cu121
numpy<2.0.0
EOF
echo "wrote $BASE/constraints.txt"

echo "=== verify ==="
python -c "import torch; print('torch', torch.__version__, '| cuda', torch.version.cuda, '| available', torch.cuda.is_available())"
pip cache purge 2>&1 | tail -1
du -sh "$BASE/venv"
echo TORCH_FIX_DONE
