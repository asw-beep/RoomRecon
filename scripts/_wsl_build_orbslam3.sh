#!/bin/bash
# scratch - builds ORB-SLAM3 core library + monocular examples only.
# Two patches applied:
#   1. C++11 -> C++17 (Pangolin 0.9.x requires C++17)
#   2. CMakeLists trimmed to monocular-only targets. The stereo/RGB-D/inertial and
#      Examples_old targets reference source trees we pruned (out of scope per ADR-002,
#      monocular RGB only) and CMake fails on the missing sources.
set -e
BASE=/home/aswin/roomrecon
SRC="$BASE/toolchain/ORB_SLAM3"
cd "$SRC"

if ! grep -q 'ROOMRECON_MONOCULAR_ONLY' CMakeLists.txt; then
  # keep everything up to the end of the core library definition (line 138), drop all examples
  head -n 138 CMakeLists.txt > CMakeLists.txt.new
  cat >> CMakeLists.txt.new <<'EOF'

# ROOMRECON_MONOCULAR_ONLY
# Monocular examples only - stereo/RGB-D/inertial and Examples_old targets removed,
# their sources are not checked out (out of scope per ADR-002).
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/Examples/Monocular)

add_executable(mono_tum Examples/Monocular/mono_tum.cc)
target_link_libraries(mono_tum ${PROJECT_NAME})

add_executable(mono_kitti Examples/Monocular/mono_kitti.cc)
target_link_libraries(mono_kitti ${PROJECT_NAME})

add_executable(mono_euroc Examples/Monocular/mono_euroc.cc)
target_link_libraries(mono_euroc ${PROJECT_NAME})

add_executable(mono_tum_vi Examples/Monocular/mono_tum_vi.cc)
target_link_libraries(mono_tum_vi ${PROJECT_NAME})
EOF
  mv CMakeLists.txt.new CMakeLists.txt
  echo "CMakeLists trimmed to monocular-only"
fi

cd "$SRC"
rm -rf build && mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release 2>&1 | tail -6
make -j"$(nproc)" 2>&1 | tail -25
echo ORBSLAM3_BUILD_DONE
