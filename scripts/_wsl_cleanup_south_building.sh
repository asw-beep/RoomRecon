#!/bin/bash
# Removes the south-building (outdoor) dataset and its 3DGS run, superseded by the
# Deep Blending indoor scenes. Its measurements are already recorded in docs/m1-downloads.csv;
# the small stats JSONs are preserved as M1 evidence before the bulk data goes.
set -e
BASE=/home/aswin/roomrecon
KEEP="$BASE/logs/m1-evidence-south-building"
RUN="$BASE/work/south-building-960/3dgs_cap250000_steps7000"
mkdir -p "$KEEP"

# preserve the evidence that is small and not reproducible without a rerun
[ -d "$RUN/stats" ] && cp -r "$RUN/stats" "$KEEP/" 2>/dev/null || true
[ -f "$RUN/cfg.yml" ] && cp "$RUN/cfg.yml" "$KEEP/" 2>/dev/null || true
for f in log_extract.txt log_match.txt log_map.txt; do
  [ -f "$BASE/work/south-building-960/$f" ] && cp "$BASE/work/south-building-960/$f" "$KEEP/" || true
done
echo "preserved:"; ls -R "$KEEP" | head -20

echo "--- freeing ---"
du -sh "$BASE/datasets/south-building" "$BASE/work/south-building-960" 2>/dev/null
rm -rf "$BASE/datasets/south-building" "$BASE/work/south-building-960"
rm -f "/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/storage/projects/m1-spike/gaussian/scene.ply"
echo "--- after ---"
du -sh "$BASE"/* 2>/dev/null | sort -rh
df -h / | tail -1
echo CLEANUP_DONE
