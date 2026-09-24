#!/bin/bash
# scratch probe - inspects the pip-installed CUDA layout inside the venv
source ~/roomrecon/venv/bin/activate
NV=$(python -c 'import nvidia, os; print(os.path.dirname(nvidia.__file__))')
echo "nvidia pkg root: $NV"
echo "--- subpackages ---"
ls "$NV"
echo "--- nvcc binary ---"
find "$NV" -name nvcc -type f 2>/dev/null
echo "--- nvcc version ---"
"$NV/cuda_nvcc/bin/nvcc" --version 2>&1 | tail -3
echo "--- cuda_runtime headers ---"
ls "$NV/cuda_runtime/include/" 2>/dev/null | head -5
echo "--- cudart lib ---"
find "$NV" -name 'libcudart*' 2>/dev/null | head -3
