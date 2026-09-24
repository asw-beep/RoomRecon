#!/bin/bash
# scratch helper, not part of the tracked toolchain - measures installed sizes for the download log
# usage: _wsl_measure.sh <substring matching the apt history Commandline entry>
python3 - "$1" <<'PYEOF'
import re, subprocess, sys
needle = sys.argv[1]
log = open('/var/log/apt/history.log', errors='ignore').read()
blocks = log.split('\n\n')
hit = [b for b in blocks if needle in b and 'Install:' in b]
if not hit:
    print('no matching apt history block'); sys.exit(1)
block = hit[-1]
inst = re.search(r'Install: (.+?)(?:\nEnd-Date|\Z)', block, re.S).group(1)
pkgs = re.findall(r'([a-z0-9][a-z0-9+.\-]*):amd64 \(', inst) + re.findall(r'([a-z0-9][a-z0-9+.\-]*):all \(', inst)
pkgs = sorted(set(pkgs))
total = 0
for p in pkgs:
    r = subprocess.run(['dpkg-query', '-W', '-f=${Installed-Size}', p],
                       capture_output=True, text=True)
    try:
        total += int(r.stdout.strip())
    except ValueError:
        pass
print(f'packages={len(pkgs)}')
print(f'total_kb={total}')
print(f'total_mb={total // 1024}')
PYEOF
