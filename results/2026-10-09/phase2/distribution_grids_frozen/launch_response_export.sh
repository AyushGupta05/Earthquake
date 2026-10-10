#!/bin/bash
set -u
cd /home/ec2-user/response_export_a338babb || exit 2
runlog=/mnt/eew-research/runs/response_prefix_export_v1.log
exec >> "$runlog" 2>&1
/home/ec2-user/Earthquake/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('.')
m=p/'bundle_manifest.json'
assert hashlib.sha256(m.read_bytes()).hexdigest()=='a338babbf27bdbeceed2235bf6f99698589e5a8750b8854fcb109c0430ec30e6'
for name,item in json.loads(m.read_text())['files'].items():
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==item['sha256'],name
assert not Path('/mnt/eew-research/runs/response_prefix_export_v1').exists()
print('Verified export bundle and fresh destination',flush=True)
PY
verified=$?
if [ "$verified" -ne 0 ]; then exit "$verified"; fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.started"
printf '1800\n' > "$runlog.timeout_seconds"
printf '%s\n' "$$" > "$runlog.pid"
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES OPENBLAS_NUM_THREADS OMP_NUM_THREADS MKL_NUM_THREADS
timeout --signal=TERM --kill-after=60s 1800s /home/ec2-user/Earthquake/.venv/bin/python -u work/response_conditioned_encoder/export_waveforms.py --polarization-source /home/ec2-user/polarization_extraction_b0ef777 --polarization-output /mnt/eew-research/runs/polarization_preflight_v2 --response-audit /home/ec2-user/response_export_a338babb/work/response_conditioned_encoder/full_response_audit_v3 --polarization-manifest-sha256 0993d321e4e21a0e612c05b01189d54b2577f5ebb238ee52ebd50300109250bb --response-join-sha256 d65966518a3ec62e022351c6fc6be91e5003c20a916cf5640b8aaba8f59d8ab2 --output /mnt/eew-research/runs/response_prefix_export_v1 --execute
status=$?
printf '%s\n' "$status" > "$runlog.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.finished"
exit "$status"
