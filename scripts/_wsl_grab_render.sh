#!/bin/bash
R=/home/aswin/roomrecon/work/south-building-960/3dgs_cap250000_steps7000
DEST="/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/storage/projects/m1-spike"
echo "=== run dir ==="
find "$R" -maxdepth 2 -type d
echo "=== images/videos produced ==="
find "$R" \( -name '*.png' -o -name '*.jpg' -o -name '*.mp4' \) | head -10
# pull one eval render + a frame from the trajectory video for visual inspection
IMG=$(find "$R" -name '*.png' | head -1)
if [ -n "$IMG" ]; then cp "$IMG" "$DEST/eval_render.png"; echo "copied eval render: $IMG"; fi
VID=$(find "$R" -name '*.mp4' | head -1)
if [ -n "$VID" ]; then
  ffmpeg -v error -y -i "$VID" -vf "select=eq(n\,30)" -vframes 1 "$DEST/traj_frame.png"
  echo "extracted traj frame from: $VID"
fi
ls -lh "$DEST"/*.png 2>/dev/null
