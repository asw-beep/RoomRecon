#!/bin/bash
D=/home/aswin/roomrecon/datasets/deepblending/db
DEST="/mnt/e/IIITK CLASS/SEM-7/Computer_vision/Project/storage/projects/m1-spike"
for s in playroom drjohnson; do
  f=$(ls "$D/$s/images/"*.jpg 2>/dev/null | head -1)
  n=$(ls "$D/$s/images/" 2>/dev/null | wc -l)
  if [ -n "$f" ]; then
    ffmpeg -v error -y -i "$f" -vf scale=640:-1 "$DEST/sample_$s.png"
    dims=$(ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0 "$f")
    echo "$s: $n images, native $dims, sample=$(basename "$f")"
  else
    echo "$s: no images found"
  fi
done
du -sh "$D"/playroom "$D"/drjohnson
