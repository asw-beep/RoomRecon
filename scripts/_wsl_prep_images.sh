#!/bin/bash
# scratch - downscales the south-building images to the T1 working resolution (960px wide).
# COLMAP here is a CPU-only build and the VRAM budget is ~5GB, so full 3072x2304 is not viable.
set -e
BASE=/home/aswin/roomrecon
SRC="$BASE/datasets/south-building/images"
DST="$BASE/work/south-building-960/images"
mkdir -p "$DST"

count=$(ls "$SRC"/*.JPG | wc -l)
echo "downscaling $count images to 960px wide..."
ls "$SRC"/*.JPG | xargs -P 8 -I{} bash -c '
  f="{}"
  out="'"$DST"'/$(basename "$f")"
  [ -f "$out" ] || ffmpeg -v error -i "$f" -vf scale=960:-1 -q:v 2 "$out"
'
echo "done: $(ls "$DST" | wc -l) images, $(du -sh "$DST" | cut -f1)"
ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0 "$DST/$(ls "$DST" | head -1)"
