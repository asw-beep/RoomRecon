#!/bin/bash
# Kept so existing commands and docs work: bash push.sh push|status|fetch ...
# The logic lives in scripts/kaggle/push.sh, shared by every Kaggle job.
exec bash "$(cd "$(dirname "$0")" && pwd)/../push.sh" m1_t2 "$@"
