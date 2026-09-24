#!/bin/bash
# scratch - downloads TUM RGB-D sequences (only rgb/ + groundtruth are used; depth is deleted)
set -e
D=/home/aswin/roomrecon/datasets/tum
mkdir -p "$D"; cd "$D"
for seq in "$@"; do
  case $seq in fr1_*) grp=freiburg1;; fr2_*) grp=freiburg2;; fr3_*) grp=freiburg3;; esac
  name="rgbd_dataset_${grp}_${seq#fr?_}"
  if [ -d "$name/rgb" ]; then echo "have $name"; continue; fi
  wget -q "https://cvg.cit.tum.de/rgbd/dataset/$grp/$name.tgz" -O "$name.tgz"
  ls -lh "$name.tgz"
  tar xzf "$name.tgz" && rm "$name.tgz"
  rm -rf "$name/depth" "$name/depth.txt"
  echo "$name: $(ls $name/rgb | wc -l) frames, $(du -sh $name | cut -f1)"
done
