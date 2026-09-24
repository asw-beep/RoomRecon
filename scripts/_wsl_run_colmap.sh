#!/bin/bash
# scratch - runs COLMAP sparse SfM on the downscaled south-building set and times each stage.
# The apt COLMAP build has no CUDA, so SIFT extraction/matching are forced to CPU.
set -e
BASE=/home/aswin/roomrecon
WORK="$BASE/work/south-building-960"
DB="$WORK/database.db"
IMAGES="$WORK/images"
SPARSE="$WORK/sparse"
mkdir -p "$SPARSE"

stage() { echo "=== $1 === $(date +%H:%M:%S)"; }

stage "feature_extraction"
t0=$(date +%s)
colmap feature_extractor \
  --database_path "$DB" \
  --image_path "$IMAGES" \
  --ImageReader.single_camera 1 \
  --ImageReader.camera_model SIMPLE_RADIAL \
  --SiftExtraction.use_gpu 0 \
  --SiftExtraction.num_threads 8 > "$WORK/log_extract.txt" 2>&1
t1=$(date +%s); echo "feature extraction: $((t1-t0))s"

stage "exhaustive_matching"
colmap exhaustive_matcher \
  --database_path "$DB" \
  --SiftMatching.use_gpu 0 \
  --SiftMatching.num_threads 8 > "$WORK/log_match.txt" 2>&1
t2=$(date +%s); echo "matching: $((t2-t1))s"

stage "mapping"
colmap mapper \
  --database_path "$DB" \
  --image_path "$IMAGES" \
  --output_path "$SPARSE" \
  --Mapper.num_threads 8 > "$WORK/log_map.txt" 2>&1
t3=$(date +%s); echo "mapping: $((t3-t2))s"
echo "TOTAL: $((t3-t0))s"

stage "result"
colmap model_analyzer --path "$SPARSE/0" 2>&1 | tail -10
echo COLMAP_DONE
