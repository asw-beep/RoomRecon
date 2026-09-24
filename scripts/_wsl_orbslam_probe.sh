#!/bin/bash
# scratch - inspects ORB-SLAM3 build state before the first TUM run
S=/home/aswin/roomrecon/toolchain/ORB_SLAM3
ls "$S"; echo ---; ls -la "$S/Vocabulary" "$S/lib"; echo ---; ls "$S/Examples/Monocular"
echo ---; grep -n "System SLAM" "$S/Examples/Monocular/mono_tum.cc"
echo ---; grep -n -i "saveTrajectory\|SaveKeyFrame" "$S/Examples/Monocular/mono_tum.cc"
echo ---; cd "$S" && git log --oneline -1 && git status --short | head
