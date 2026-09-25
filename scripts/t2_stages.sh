# Shared stage runner for T2 (Kaggle) entry scripts. Source it after setting $STAGES.
# Same contract as scripts/run_t2.sh (which predates it and keeps its own copy):
#   - every stage is appended to $STAGES as JSON with status, exit code and wall time;
#   - a required stage failing stops the session (exit -> the caller's EXIT trap still
#     writes the verdict); a best-effort failure is recorded and the session goes on.

# stage <name> <required|best_effort> <command...>
stage() {
  local name=$1 kind=$2; shift 2
  local t0 rc status
  echo; echo "=== $name ($kind) ==="
  t0=$(date +%s)
  "$@"; rc=$?
  status=$([ $rc -eq 0 ] && echo ok || echo failed)
  printf '{"name":"%s","required":%s,"status":"%s","exit_code":%d,"wall_s":%d}\n' \
    "$name" "$([ "$kind" = required ] && echo true || echo false)" "$status" $rc $(( $(date +%s) - t0 )) >> "$STAGES"
  echo "--- $name: $status (exit $rc, $(( $(date +%s) - t0 ))s)"
  if [ $rc -ne 0 ] && [ "$kind" = required ]; then
    echo "required stage '$name' failed - stopping; verdict and package still run"
    exit $rc
  fi
  return 0
}

# find_input <path suffix>: first directory under /kaggle/input ending in the suffix.
# Where Kaggle mounts an attached notebook's output is not documented; search, don't assume.
find_input() {
  find -L /kaggle/input -maxdepth 6 -type d -path "*$1" 2>/dev/null | head -1
}

# ---- the GPU session preamble shared by training entry scripts (as in run_t2.sh).
# Need: $REPO $OUT $SCRATCH set, $OUT/logs present.

pin_gpu() {
  python3 scripts/gpu.py > "$OUT/logs/gpus.json" || return 1
  CUDA_VISIBLE_DEVICES=$(python3 scripts/gpu.py --pin) || return 1
  export CUDA_VISIBLE_DEVICES
  echo "$(python3 -c "import json;print(len(json.load(open('$OUT/logs/gpus.json'))))") GPU(s); pinned to $CUDA_VISIBLE_DEVICES"
}

setup() {
  bash scripts/setup_t2.sh > "$OUT/logs/setup_t2.log" 2>&1; local rc=$?
  tail -25 "$OUT/logs/setup_t2.log"
  [ $rc -eq 0 ] || return $rc
  source "$SCRATCH/venv/bin/activate"
  export CUDA_HOME=/usr/local/cuda-12.1 PATH=/usr/local/cuda-12.1/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64:${LD_LIBRARY_PATH:-}
  export ROOMRECON_TOOLCHAIN="$SCRATCH/toolchain"
  export TORCH_CUDA_ARCH_LIST="$(nvidia-smi --id="$CUDA_VISIBLE_DEVICES" --query-gpu=compute_cap --format=csv,noheader)"
  pip freeze > "$OUT/logs/env_freeze.txt"
}

verify() {
  python scripts/verify_env.py --json > "$OUT/verify_env.json"; local rc=$?
  python - "$OUT/verify_env.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for c in d["checks"]:
    print(f"  {'PASS' if c['ok'] else ('FAIL' if c['required'] else 'n/a ')}  {c['check']:<20} {c['detail']}")
PY
  return $rc
}

# restore_work: bring back this job's previous work/ (push.sh push --continue). Required
# when continuing: asked to continue but nothing found means stop before re-spending GPU.
restore_work() {
  local prev found=()
  while IFS= read -r prev; do
    compgen -G "$prev/*/run.json" >/dev/null || continue
    cp -rn "$prev/." "$OUT/work/" && found+=("$prev") && echo "restored $prev"
  done < <(find /kaggle/input -maxdepth 6 -type d -name work 2>/dev/null)
  python3 - "$OUT/logs/restore.json" "${found[@]}" <<'PY'
import json, sys
from pathlib import Path
out, sources = sys.argv[1], sys.argv[2:]
runs = sorted({p.parent.name for s in sources for p in Path(s).glob("*/run.json")})
json.dump({"restored_from": sources, "runs": runs}, open(out, "w"), indent=1)
print(f"{len(runs)} run(s) restored: {runs}" if runs else "no previous session attached - fresh start")
PY
  [ "${CONTINUE:-0}" != 1 ] || [ ${#found[@]} -gt 0 ]
}
