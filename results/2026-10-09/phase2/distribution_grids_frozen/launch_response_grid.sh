#!/bin/bash
set -u
cd /home/ec2-user/distribution_grids_7204ab1d || exit 2
runlog=/mnt/eew-research/runs/response_architecture_grid_v1.log
exec >> "$runlog" 2>&1
/home/ec2-user/Earthquake/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('.')
m=p/'bundle_manifest.json'
assert hashlib.sha256(m.read_bytes()).hexdigest()=='7204ab1d6502599565478a641a824cd92a1028bf81b6410360845d79c682362f'
for name,item in json.loads(m.read_text())['files'].items():
 assert hashlib.sha256((p/name).read_bytes()).hexdigest()==item['sha256'],name
assert not Path('/mnt/eew-research/runs/response_architecture_grid_v1').exists()
assert hashlib.sha256(Path('/mnt/eew-research/runs/response_prefix_export_v1/manifest.json').read_bytes()).hexdigest()=='55ba19f81f59c106964ae92302258aba7780d5bc1a48cd3ec20617c8f2ba2a46'
assert json.loads(Path('/mnt/eew-research/runs/response_prefix_export_v1/COMPLETE.json').read_text())['manifest_sha256']=='55ba19f81f59c106964ae92302258aba7780d5bc1a48cd3ec20617c8f2ba2a46'
print('Verified reviewed bundle, pinned export and fresh destination',flush=True)
PY
verified=$?
if [ "$verified" -ne 0 ]; then exit "$verified"; fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.started"
printf '6800\n' > "$runlog.timeout_seconds"
printf '%s\n' "$$" > "$runlog.pid"
CUDA_VISIBLE_DEVICES='0' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES OPENBLAS_NUM_THREADS OMP_NUM_THREADS MKL_NUM_THREADS
timeout --signal=TERM --kill-after=60s 6800s /home/ec2-user/Earthquake/.venv/bin/python -u work/response_conditioned_encoder/train_response_grid.py --export /mnt/eew-research/runs/response_prefix_export_v1 --bundle /home/ec2-user/distribution_grids_7204ab1d/work/response_conditioned_encoder/training_source_manifest.json --bundle-sha256 f745a18b194490b2f018845ddeeb5a3282aa9a0307a4795cfebe465382b669d3 --output /mnt/eew-research/runs/response_architecture_grid_v1 --execute
status=$?
printf '%s\n' "$status" > "$runlog.exit"
date -u +%Y-%m-%dT%H:%M:%SZ > "$runlog.finished"
exit "$status"
