#!/bin/bash
# scratch - installs fused-ssim, the last gsplat example dep.
# Needs --no-build-isolation (its setup.py imports torch) and -c constraints.txt so it
# cannot drag in a different torch again.
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"
export CUDA_HOME=/usr/local/cuda-12.1
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="8.6"

pip install --no-build-isolation --no-cache-dir -c "$BASE/constraints.txt" \
  "git+https://github.com/rahul-goel/fused-ssim@328dc9836f513d00c4b5bc38fe30478b4435cbb5" \
  2>&1 | tail -6

echo "=== verify torch still pinned ==="
python -c "import torch; print('torch', torch.__version__, '| cuda available', torch.cuda.is_available())"
python -c "import fused_ssim; print('fused_ssim import OK')"
echo FUSED_SSIM_DONE
