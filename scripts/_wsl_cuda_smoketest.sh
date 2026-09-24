#!/bin/bash
# scratch - proves nvcc + torch can actually compile and run a CUDA extension
set -e
source ~/roomrecon/venv/bin/activate
export CUDA_HOME=/usr/local/cuda-12.1
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

mkdir -p ~/roomrecon/logs/cuda_smoketest
cd ~/roomrecon/logs/cuda_smoketest

cat > kernel.cu <<'EOF'
#include <torch/extension.h>
__global__ void add_one_kernel(float* x, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) x[i] += 1.0f;
}
void add_one(torch::Tensor x) {
    int n = x.numel();
    int threads = 256;
    int blocks = (n + threads - 1) / threads;
    add_one_kernel<<<blocks, threads>>>(x.data_ptr<float>(), n);
}
PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("add_one", &add_one, "add one (CUDA)");
}
EOF

python - <<'PYEOF'
import time, torch
from torch.utils.cpp_extension import load

t0 = time.time()
ext = load(name='smoketest', sources=['kernel.cu'], verbose=False)
print(f'extension compiled in {time.time()-t0:.1f}s')

x = torch.zeros(1024, device='cuda')
ext.add_one(x)
torch.cuda.synchronize()
assert x.mean().item() == 1.0, f'expected 1.0, got {x.mean().item()}'
print('CUDA kernel executed correctly on GPU')
print(f'peak VRAM during test: {torch.cuda.max_memory_allocated()/1024**2:.1f} MB')
free, total = torch.cuda.mem_get_info()
print(f'GPU memory: {(total-free)/1024**3:.2f} GB used / {total/1024**3:.2f} GB total')
PYEOF
