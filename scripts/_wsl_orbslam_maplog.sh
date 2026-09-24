#!/bin/bash
L=/home/aswin/roomrecon/work/orbslam3/$1/run1/log.txt
grep -n -i "map\|init\|lost\|fail\|reset" "$L" | head -30; echo ...; wc -l "$L"
