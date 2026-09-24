#!/bin/bash
# waits for gsplat to write its first eval render, then copies it out for inspection
R=/home/aswin/roomrecon/work/drjohnson_cap1000000_steps15000
DEST="/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/storage/projects/m1-spike"
for i in $(seq 1 180); do
  f=$(ls "$R"/renders/*.png 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    cp "$f" "$DEST/drjohnson_eval.png"
    echo "FOUND: $f"
    cat "$R"/stats/val*.json 2>/dev/null
    exit 0
  fi
  sleep 10
done
echo "TIMEOUT - no render after 30min"
