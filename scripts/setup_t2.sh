#!/bin/bash
# T2 (Kaggle) cold-start setup: bare session -> environment that passes verify_env.py.
#
#   git clone <repo> && bash roomrecon/scripts/setup_t2.sh
#
# Rebuilds the T1 stack from pins (configs/constraints.txt) rather than trusting the
# preinstalled Kaggle torch, so both tiers train with the same versions. ORB-SLAM3 and
# COLMAP are deliberately absent: pose estimation is T1-only (ADR-005 constraint 1).
#
# Prints the wall time of every phase - T2 setup cost counts against the weekly GPU
# quota and is an M1 baseline.
#
# STATUS: written from the T1 install; not yet run on Kaggle.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="${ROOMRECON_T2_ROOT:-/tmp/roomrecon}"   # scratch, not /kaggle/working (outputs)
VENV="$ROOT/venv"
export ROOMRECON_TOOLCHAIN="$ROOT/toolchain"
export MPLBACKEND=Agg   # Kaggle's inline Jupyter backend is not in our venv
C="$REPO/configs/constraints.txt"
mkdir -p "$ROOT" "$ROOMRECON_TOOLCHAIN"

T0=$(date +%s); LAST=$T0
phase() { local now; now=$(date +%s); echo "--- [$((now-LAST))s] $1 done"; LAST=$now; }

echo "=== system ==="
. /etc/os-release; echo "$PRETTY_NAME"
nvidia-smi --query-gpu=name,memory.total,compute_cap,driver_version --format=csv,noheader
ARCH=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)
export TORCH_CUDA_ARCH_LIST="$ARCH"   # build kernels for this GPU only

echo "=== python 3.10 venv (uv) ==="
pip install -q uv
uv python install 3.10
uv venv --clear --seed -p 3.10 "$VENV"   # --clear: a rerun in the same session starts clean
source "$VENV/bin/activate"
phase python

echo "=== nvcc 12.1 (must match torch cu121 for extension builds) ==="
export CUDA_HOME=/usr/local/cuda-12.1
if [ ! -x "$CUDA_HOME/bin/nvcc" ]; then
  [ "$VERSION_ID" = "22.04" ] || { echo "nvcc install path assumes Ubuntu 22.04, got $VERSION_ID"; exit 1; }
  wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
    -O /tmp/cuda-keyring.deb
  dpkg -i /tmp/cuda-keyring.deb
  apt-get update -qq
  apt-get install -y -qq cuda-nvcc-12-1 cuda-cudart-dev-12-1
fi
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}
phase nvcc

echo "=== torch stack ==="
pip install -q -c "$C" torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install -q -c "$C" numpy ninja gsplat
phase torch

echo "=== gsplat examples + RoomRecon resume patch ==="
G="$ROOMRECON_TOOLCHAIN/gsplat"
[ -d "$G" ] || git clone -q --depth 1 --branch v1.5.3 https://github.com/nerfstudio-project/gsplat.git "$G"
git -C "$G" apply --check "$REPO/scripts/patches/gsplat-1.5.3-resume.patch" 2>/dev/null \
  && git -C "$G" apply "$REPO/scripts/patches/gsplat-1.5.3-resume.patch" \
  || grep -q _save_resume "$G/examples/simple_trainer.py"   # already applied
pip install -q -c "$C" \
  "git+https://github.com/rmbrualla/pycolmap@cc7ea4b7301720ac29287dbe450952511b32125e" \
  viser \
  "git+https://github.com/nerfstudio-project/nerfview@4538024fe0d15fd1a0e4d760f3695fc44ca72787" \
  "imageio[ffmpeg]" scikit-learn tqdm "torchmetrics[image]" opencv-python "tyro>=0.8.8" \
  Pillow tensorboard tensorly pyyaml matplotlib splines
# setup.py imports torch, so no build isolation
pip install -q --no-build-isolation -c "$C" \
  "git+https://github.com/rahul-goel/fused-ssim@328dc9836f513d00c4b5bc38fe30478b4435cbb5"
phase gsplat

echo "=== verify ==="
python "$REPO/scripts/verify_env.py"
echo "=== T2 setup total $(( $(date +%s) - T0 ))s ==="
echo "activate with: source $VENV/bin/activate && export CUDA_HOME=$CUDA_HOME PATH=$CUDA_HOME/bin:\$PATH ROOMRECON_TOOLCHAIN=$ROOMRECON_TOOLCHAIN"
