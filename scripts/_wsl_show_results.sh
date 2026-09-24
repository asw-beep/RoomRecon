#!/bin/bash
R=/home/aswin/roomrecon/work/south-building-960/3dgs_cap250000_steps7000
echo "=== stats dir ==="
ls -la "$R/stats/"
echo "=== stats contents ==="
for f in "$R"/stats/*; do echo "--- $f ---"; cat "$f"; echo; done
echo "=== ply / ckpt ==="
ls -lh "$R/ply/" "$R/ckpts/"
echo "=== peak vram (MiB, incl desktop baseline) ==="
sort -n "$R/vram_samples.txt" | tail -1
echo "=== baseline vram (MiB, idle) ==="
sort -n "$R/vram_samples.txt" | head -1
