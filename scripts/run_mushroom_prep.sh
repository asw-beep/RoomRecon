#!/bin/bash
# M1 MuSHRoom, part 1 of 2, on a T2 CPU session: fetch the rooms and build the two
# COLMAP datasets per room (scripts/mushroom_prepare.py). CPU-only work runs here, off
# the GPU quota (ADR-007). Launched by: bash scripts/kaggle/push.sh m1_mushroom_prep push
# Part 2 (scripts/run_mushroom_train.sh) attaches this session's output.
#
# Same contract as run_t2.sh: stages recorded, the verdict is the exit code and is always
# written, results go straight to $OUT, reruns skip what is done.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOMRECON_T2_OUT:-/kaggle/working}"
SCRATCH="${ROOMRECON_T2_ROOT:-/tmp/roomrecon}"
ROOMS="${MUSHROOM_ROOMS:-koivu vr_room}"
CONTINUE="${ROOMRECON_T2_CONTINUE:-0}"
T0=$(date +%s)
mkdir -p "$OUT/logs" "$OUT/rooms"
STAGES="$OUT/stages.jsonl"; : > "$STAGES"
printf '{"continue":%s,"rooms":"%s"}\n' "$([ "$CONTINUE" = 1 ] && echo true || echo false)" "$ROOMS" \
  > "$OUT/logs/session.json"
cd "$REPO"
# shellcheck source=t2_stages.sh
source scripts/t2_stages.sh

tools() {
  # COLMAP from the distribution: CPU build, which is all this session has.
  { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq colmap; } \
    > "$OUT/logs/apt_colmap.log" 2>&1 || { tail -20 "$OUT/logs/apt_colmap.log"; return 1; }
  python3 -c "import numpy" 2>/dev/null \
    || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-numpy >> "$OUT/logs/apt_colmap.log" 2>&1
  # each check on its own line: in a function only the LAST command sets the exit status
  command -v colmap >/dev/null || { echo "colmap not installed"; return 1; }
  python3 -c "import numpy" || { echo "numpy not importable"; return 1; }
  { colmap -h | head -2
    python3 -c "import numpy; print('numpy', numpy.__version__)"
    echo "cpus $(nproc)"; } | tee "$OUT/logs/colmap_version.txt"
}

restore() {
  # push --continue: rooms finished by the previous session are copied back, not redone
  local prev n=0 f
  prev=$(find_input "/rooms")
  [ -n "$prev" ] || { echo "no previous session attached"; [ "$CONTINUE" != 1 ]; return; }
  for f in "$prev"/*; do
    [ -e "$OUT/rooms/$(basename "$f")" ] || { cp "$f" "$OUT/rooms/" && n=$((n + 1)); }
  done
  echo "restored $n file(s) from $prev"
}

fetch() {
  # shellcheck disable=SC2086
  python3 scripts/fetch_mushroom.py --dest "$SCRATCH/mushroom" $ROOMS | tee "$OUT/logs/fetch.json"
}

prepare_room() {
  local room=$1 dst="$SCRATCH/prep/$room"
  if [ -f "$OUT/rooms/mushroom_$room.tar" ] && [ -f "$OUT/rooms/$room.prep_report.json" ]; then
    echo "$room already prepared"; return 0
  fi
  rm -rf "$dst"; mkdir -p "$SCRATCH/prep" "$OUT/logs/$room"
  python3 scripts/mushroom_prepare.py "$SCRATCH/mushroom/room_datasets/$room/iphone" "$dst" \
    --vocab-tree "$SCRATCH/mushroom/vocab_tree_flickr100K_words32K.bin" > "$OUT/logs/$room/prepare.log" 2>&1
  local rc=$?
  cp "$dst"/_colmap/*.log "$OUT/logs/$room/" 2>/dev/null
  tail -40 "$OUT/logs/$room/prepare.log"
  [ $rc -eq 0 ] || return $rc
  # one file per room: session outputs may drop symlinks and cap file counts
  tar cf "$OUT/rooms/mushroom_$room.tar.tmp" -C "$SCRATCH/prep" --exclude="$room/_colmap" "$room" \
    && mv "$OUT/rooms/mushroom_$room.tar.tmp" "$OUT/rooms/mushroom_$room.tar" \
    && cp "$dst/prep_report.json" "$OUT/rooms/$room.prep_report.json"
}

finish() {
  trap - EXIT
  echo; echo "=== verdict ==="
  # shellcheck disable=SC2086
  python3 scripts/mushroom_verdict.py prep --out "$OUT" --rooms $ROOMS; local verdict=$?
  echo "=== package ==="
  (cd "$OUT" && tar czf m1_mushroom_prep_artifact.tar.gz --ignore-failed-read \
     verdict.json stages.jsonl logs $(ls rooms/*.prep_report.json 2>/dev/null)) \
    && ls -lh "$OUT/m1_mushroom_prep_artifact.tar.gz"
  echo "=== session total $(( $(date +%s) - T0 ))s ==="
  exit $verdict
}
trap finish EXIT

stage "tools"   required tools
stage "restore" "$([ "$CONTINUE" = 1 ] && echo required || echo best_effort)" restore
stage "fetch"   required fetch
for room in $ROOMS; do
  stage "prepare $room" required prepare_room "$room"
done
