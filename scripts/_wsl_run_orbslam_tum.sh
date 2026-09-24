#!/bin/bash
# scratch - runs headless ORB-SLAM3 monocular on a TUM sequence N times and evaluates ATE.
# ORB-SLAM3 is multithreaded and not deterministic, so repeat runs are the only honest
# way to report its accuracy.
#
# usage: _wsl_run_orbslam_tum.sh <seq dir name> <TUM1|TUM2|TUM3> [runs=3]
set -e
BASE=/home/aswin/roomrecon
S=$BASE/toolchain/ORB_SLAM3
SEQ=$BASE/datasets/tum/$1
CFG=$S/Examples/Monocular/$2.yaml
RUNS=${3:-3}
EVAL="/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/scripts/_wsl_eval_ate.py"
source "$BASE/venv/bin/activate"
export ORB_NO_VIEWER=1
export LD_LIBRARY_PATH=$S/lib:$S/Thirdparty/DBoW2/lib:$S/Thirdparty/g2o/lib:/usr/local/lib:$LD_LIBRARY_PATH

echo "=== $1  ($(wc -l < "$SEQ/rgb.txt") rgb.txt lines, cfg $2) ==="
for r in $(seq 1 "$RUNS"); do
  OUT=$BASE/work/orbslam3/$1/run$r
  mkdir -p "$OUT"; cd "$OUT"
  START=$(date +%s.%N)
  /usr/bin/time -v "$S/Examples/Monocular/mono_tum" "$S/Vocabulary/ORBvoc.txt" "$CFG" "$SEQ" \
    > log.txt 2> time.txt || echo "run$r EXIT $?"
  END=$(date +%s.%N)
  echo "--- run$r wall $(printf '%.1f' "$(echo "$END - $START" | bc)")s," \
       "peak RSS $(grep 'Maximum resident' time.txt | awk '{printf "%.0f MiB", $NF/1024}')," \
       "maps created: $(grep -c 'Creation of new map with id' log.txt || true)," \
       "resets: $(grep -ci 'reseting' log.txt || true)"
  grep -i "median tracking time\|mean tracking time" log.txt || true
  if [ -s KeyFrameTrajectory.txt ]; then
    python "$EVAL" "$SEQ/groundtruth.txt" KeyFrameTrajectory.txt | tee ate.json
  else
    echo "NO TRAJECTORY"; tail -5 log.txt
  fi
done
