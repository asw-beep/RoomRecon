#!/bin/bash
# scratch - makes mono_tum's Pangolin viewer optional (ORB_NO_VIEWER=1 -> headless),
# then rebuilds only the mono_tum target.
set -e
S=/home/aswin/roomrecon/toolchain/ORB_SLAM3
F="$S/Examples/Monocular/mono_tum.cc"
if ! grep -q ORB_NO_VIEWER "$F"; then
  sed -i 's|ORB_SLAM3::System SLAM(argv\[1\],argv\[2\],ORB_SLAM3::System::MONOCULAR,true);|ORB_SLAM3::System SLAM(argv[1],argv[2],ORB_SLAM3::System::MONOCULAR,getenv("ORB_NO_VIEWER")==nullptr);|' "$F"
  grep -q '#include<cstdlib>' "$F" || sed -i '0,/#include<iostream>/s//#include<iostream>\n#include<cstdlib>/' "$F"
fi
grep -n "System SLAM\|cstdlib" "$F"
cd "$S/build"
make mono_tum -j4 2>&1 | tail -3
ls -la "$S/Examples/Monocular/mono_tum"
