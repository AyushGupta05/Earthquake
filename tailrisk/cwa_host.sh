#!/bin/bash
# Join the CWA training pool (PREREGISTRATION_CWA.md) on this host: wait for the cache (built on the
# second host and published to S3, or local), then serve the shared claim queue (claim_runner.py).
#   cwa_host.sh LOCAL_CACHE_DIR [build]   # 'build': this host built the cache and publishes it
C=$1; MODE=${2:-}
D=s3://instance-earthquake-data/sm/data/cwa
P=s3://instance-earthquake-data/sm/cwa
cd "$(dirname "$0")"
PY=${PY:-../.venv/bin/python}
if [ "$MODE" = build ]; then
  until grep -q " done$" /mnt/cwa/prep.log 2>/dev/null; do sleep 120; done
  for f in meta.npz wave16.npy scale.npy folds.json events.csv; do aws s3 cp $C/$f $D/$f --only-show-errors; done
  echo published > /tmp/cwa_published && aws s3 cp /tmp/cwa_published $D/_published --only-show-errors
else
  until aws s3 ls $D/_published > /dev/null 2>&1; do sleep 120; done
  mkdir -p $C
  for f in meta.npz wave16.npy scale.npy folds.json events.csv; do aws s3 cp $D/$f $C/$f --only-show-errors; done
fi
export TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5
$PY claim_runner.py --queue sm_queues/queue_cwa.txt --prefix $P --gpu 0 >> $C/claim_runner.log 2>&1
echo "$(date -u) queue exhausted" >> $C/claim_runner.log
