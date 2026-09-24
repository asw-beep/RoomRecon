#!/bin/bash
# scratch - checks runner deps and validates _wsl_eval_ate.py on a synthetic Sim(3)-transformed trajectory
which bc /usr/bin/time || echo MISSING_TOOL
source /home/aswin/roomrecon/venv/bin/activate
T=$(mktemp -d); cd "$T"
python - <<'PY'
import numpy as np
rng=np.random.default_rng(0)
t=np.arange(0,30,0.033); p=np.c_[np.sin(t),np.cos(t*0.7),0.1*t]
np.savetxt("gt.txt",np.c_[t,p,np.zeros((len(t),3)),np.ones(len(t))],fmt="%.6f")
a=0.8; R=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
q=(R@((p-[1,2,3])/2.5).T).T   # est = R*(p - c)/2.5  -> recovered scale should be 2.5
k=t[::10]; np.savetxt("est.txt",np.c_[k+0.004,q[::10],np.zeros((len(k),3)),np.ones(len(k))],fmt="%.6f")
PY
python "/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/scripts/_wsl_eval_ate.py" gt.txt est.txt
rm -rf "$T"
