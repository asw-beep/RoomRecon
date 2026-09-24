#!/bin/bash
# scratch - repairs the gutted nvidia cu12 libs and reclaims disk.
# The CUDA 13 uninstall emptied the shared nvidia/*/lib dirs while leaving pip metadata
# intact, so pip thinks they are installed. Force-reinstall is required.
set -e
BASE=/home/aswin/roomrecon
source "$BASE/venv/bin/activate"

echo "=== removing CUDA 13 leftovers ==="
rm -rf "$BASE/venv/lib/python3.10/site-packages/nvidia/cu13" \
       "$BASE/venv/lib/python3.10/site-packages/nvidia/nvshmem"

echo "=== force-reinstalling nvidia cu12 runtime libs (no cache) ==="
pip install --force-reinstall --no-cache-dir --no-deps \
  nvidia-cublas-cu12==12.1.3.1 \
  nvidia-cuda-cupti-cu12==12.1.105 \
  nvidia-cuda-nvrtc-cu12==12.1.105 \
  nvidia-cuda-runtime-cu12==12.1.105 \
  nvidia-cudnn-cu12==9.1.0.70 \
  nvidia-cufft-cu12==11.0.2.54 \
  nvidia-curand-cu12==10.3.2.106 \
  nvidia-cusolver-cu12==11.4.5.107 \
  nvidia-cusparse-cu12==12.1.0.106 \
  nvidia-nccl-cu12==2.21.5 \
  nvidia-nvjitlink-cu12==12.9.86 \
  nvidia-nvtx-cu12==12.1.105 2>&1 | tail -3

echo "=== verify torch ==="
python -c "import torch; print('torch', torch.__version__, '| cuda', torch.version.cuda, '| available', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0))"

echo "=== reclaiming disk ==="
pip cache purge 2>&1 | tail -1
rm -rf /tmp/pip-* /tmp/tmp* 2>/dev/null || true
echo "venv: $(du -sh "$BASE/venv" | cut -f1)"
echo "pip cache: $(du -sh ~/.cache/pip 2>/dev/null | cut -f1)"
echo "/tmp: $(du -sh /tmp 2>/dev/null | cut -f1)"
df -h / | tail -1
echo REPAIR_CLEAN_DONE
