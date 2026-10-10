#!/bin/bash
set -u
cd /home/ec2-user/polarization_fit_6b38d096 || exit 2
runlog=/mnt/eew-research/runs/polarization_probe_v2.fit.log
exec >> "$runlog" 2>&1
/home/ec2-user/Earthquake/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('.')
m=p/'fit_manifest.json'
assert hashlib.sha256(m.read_bytes()).hexdigest()=='6b38d0968c6f29906b4828b1eb94564e18157f8881157edb4988107612a6b4c5'
for name,item in json.loads(m.read_text())['files'].items():
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==item['sha256'],name
assert not Path('/mnt/eew-research/runs/polarization_probe_v2').exists()
print('Verified fit bundle and fresh destination',flush=True)
PY
verified=$?
if [ "$verified" -ne 0 ]; then exit "$verified"; fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.started"
printf '1860\n' > "$runlog.timeout_seconds"
printf '%s\n' "$$" > "$runlog.pid"
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES OPENBLAS_NUM_THREADS OMP_NUM_THREADS MKL_NUM_THREADS
timeout --signal=TERM --kill-after=60s 1860s /home/ec2-user/Earthquake/.venv/bin/python -u run_probe.py --cache /mnt/eew-research/runs/polarization_preflight_v2 --output /mnt/eew-research/runs/polarization_probe_v2 --execute
status=$?
printf '%s\n' "$status" > "$runlog.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.finished"
exit "$status"
