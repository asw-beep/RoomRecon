#!/bin/bash
PLY=/home/aswin/roomrecon/work/south-building-960/3dgs_cap250000_steps7000/ply/point_cloud_6999.ply
echo "=== header ==="
head -c 2000 "$PLY" | strings | sed -n '1,40p'
echo
echo "=== size ==="
ls -lh "$PLY"
