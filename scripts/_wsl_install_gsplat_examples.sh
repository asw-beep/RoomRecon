#!/bin/bash
# scratch - installs the deps gsplat's example trainer needs, in two phases.
# Phase 2 packages have setup.py files that `import torch`, which fails inside pip's
# isolated build env, so they need --no-build-isolation.
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"
export CUDA_HOME=/usr/local/cuda-12.1
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="8.6"   # RTX 3050 Laptop = Ampere sm_86; avoids building all archs

echo "=== phase 1: standard deps ==="
pip install \
  "git+https://github.com/rmbrualla/pycolmap@cc7ea4b7301720ac29287dbe450952511b32125e" \
  viser \
  "git+https://github.com/nerfstudio-project/nerfview@4538024fe0d15fd1a0e4d760f3695fc44ca72787" \
  "imageio[ffmpeg]" "numpy<2.0.0" scikit-learn tqdm "torchmetrics[image]" \
  opencv-python "tyro>=0.8.8" Pillow tensorboard tensorly pyyaml matplotlib splines \
  2>&1 | tail -6

echo "=== phase 2: CUDA-compiling deps (no build isolation) ==="
pip install --no-build-isolation \
  "git+https://github.com/rahul-goel/fused-ssim@328dc9836f513d00c4b5bc38fe30478b4435cbb5" \
  2>&1 | tail -6

echo GSPLAT_EXAMPLES_DEPS_DONE
