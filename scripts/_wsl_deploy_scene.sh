#!/bin/bash
# copies the finished drjohnson scene into the viewer spike and reports final metrics
set -e
R=/home/aswin/roomrecon/work/drjohnson_cap1000000_steps15000
DEST="/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/storage/projects/m1-spike"
echo "=== all eval stats ==="
for f in "$R"/stats/val*.json; do echo "$(basename "$f"): $(cat "$f")"; done
echo
echo "=== deploying final ply ==="
mkdir -p "$DEST/gaussian"
cp "$R/ply/point_cloud_14999.ply" "$DEST/gaussian/scene.ply"
ls -lh "$DEST/gaussian/scene.ply"
# grab a final eval render too
f=$(ls "$R"/renders/val_step14999_*.png 2>/dev/null | head -1)
[ -n "$f" ] && cp "$f" "$DEST/drjohnson_final.png" && echo "final render: $(basename "$f")"
echo "=== peak/baseline vram ==="
sort -n "$R/vram_samples.txt" | tail -1
sort -n "$R/vram_samples.txt" | head -1
