#!/bin/bash
set -u
cd /home/ec2-user/eew-work/Earthquake
log=/home/ec2-user/eew-work/full-logs/flat_station_export_v1.log
exec >> "$log" 2>&1
printf 'START '
date -u +%Y-%m-%dT%H:%M:%SZ
printf 'SOURCE_CODE_SHA '
sha256sum research/2026-10-09/phase3/flat_station_cache.py
/opt/pytorch/bin/python -u research/2026-10-09/phase3/flat_station_cache.py \
  --source /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 \
  --destination /mnt/eew-fast/chile-train-stations-v1 \
  --expected-source-cache-sha256 c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb \
  --expected-source-metadata-sha256 8840a482419afff5a54681beeb901e5a227e12e64cdf76b1faddf5b3d38285a1
export_status=$?
printf 'EXIT %s ' "$export_status"
date -u +%Y-%m-%dT%H:%M:%SZ
if [ "$export_status" -eq 0 ]; then
  cp /mnt/eew-fast/chile-train-stations-v1/manifest.json /home/ec2-user/eew-work/full-logs/flat_station_export_v1.manifest.json
  sha256sum /home/ec2-user/eew-work/full-logs/flat_station_export_v1.manifest.json
fi
exit "$export_status"
