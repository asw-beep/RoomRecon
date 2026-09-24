#!/bin/bash
# scratch - builds Pangolin (ORB-SLAM3 viewer dependency). Run as user aswin; install step needs root.
set -e
BASE=/home/aswin/roomrecon
cd "$BASE/toolchain/Pangolin"
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF \
         -DBUILD_PANGOLIN_PYTHON=OFF -DBUILD_TOOLS=OFF 2>&1 | tail -12
make -j"$(nproc)" 2>&1 | tail -12
echo PANGOLIN_BUILD_DONE
