#!/bin/bash
set -u
cd /home/ec2-user/polarization_extraction_b0ef777 || exit 2
runlog=/mnt/eew-research/runs/polarization_preflight_v2.extract.log
exec >> "$runlog" 2>&1
/home/ec2-user/Earthquake/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('.')
m=p/'extraction_manifest.json'
assert hashlib.sha256(m.read_bytes()).hexdigest()=='b0ef777b9aac96e7913f874327fbd927434787d39cb27694b2555887476fafac'
for name,item in json.loads(m.read_text())['files'].items():
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==item['sha256'],name
assert not Path('/mnt/eew-research/runs/polarization_preflight_v2').exists()
print('Verified extraction bundle and fresh destination',flush=True)
PY
verified=$?
if [ "$verified" -ne 0 ]; then exit "$verified"; fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.started"
printf '1800\n' > "$runlog.timeout_seconds"
printf '%s\n' "$$" > "$runlog.pid"
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES OPENBLAS_NUM_THREADS OMP_NUM_THREADS MKL_NUM_THREADS
timeout --signal=TERM --kill-after=60s 1800s /home/ec2-user/Earthquake/.venv/bin/python -u extract_features.py --output /mnt/eew-research/runs/polarization_preflight_v2 --execute
status=$?
printf '%s\n' "$status" > "$runlog.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.finished"
exit "$status"
