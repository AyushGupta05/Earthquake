#!/bin/bash
# Detached driver: full-precision log-posterior exports for the multi-station study (seed-1 arms).
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
  ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_$a.log 2>&1
  echo "$(date -u) export INSTANCE $a rc=$?" >> $W/logs/export_batch.log
done
for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
  TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_chile_$a.log 2>&1
  echo "$(date -u) export chile $a rc=$?" >> $W/logs/export_batch.log
done
