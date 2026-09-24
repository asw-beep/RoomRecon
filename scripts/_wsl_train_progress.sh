#!/bin/bash
R=/home/aswin/roomrecon/work/drjohnson_cap1000000_steps15000
source /home/aswin/roomrecon/venv/bin/activate
echo "=== run dir ==="
ls -la "$R" 2>/dev/null | head
echo "=== renders ==="
ls "$R/renders/" 2>/dev/null | head -5
echo "=== stats ==="
cat "$R"/stats/*.json 2>/dev/null
echo "=== progress ==="
python - "$R" <<'PY'
import glob, sys
from tensorboard.backend.event_processing import event_accumulator
fs = glob.glob(sys.argv[1] + '/tb/events*')
if not fs:
    print('no tensorboard file found at', sys.argv[1] + '/tb/')
else:
    ea = event_accumulator.EventAccumulator(fs[0]); ea.Reload()
    for t in ('train/num_GS', 'train/loss', 'train/mem'):
        if t in ea.Tags()['scalars']:
            s = ea.Scalars(t)
            print(f'{t:14s} step {s[-1].step:6d}/15000  = {s[-1].value:.4f}')
PY
nvidia-smi --query-gpu=memory.used --format=csv,noheader
