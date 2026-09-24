#!/bin/bash
# scratch - blocks until a TUM sequence is extracted (rgb/ present, tgz removed), 30 min cap
D=/home/aswin/roomrecon/datasets/tum/$1
for i in $(seq 1 360); do
  if [ -f "$D/groundtruth.txt" ] && [ ! -f "$D.tgz" ]; then echo "READY $1: $(ls $D/rgb | wc -l) frames"; exit 0; fi
  sleep 5
done
echo "TIMEOUT waiting for $1"; ls -la /home/aswin/roomrecon/datasets/tum/; exit 1
