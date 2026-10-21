#!/bin/bash
# Detached driver: GEOFON exports and multi-station study (seed 1 incl. mixdgr, then seeds 2-3).
W=/mnt/eew-research/runs/tailwork
G=$W/geofon
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
ex() { TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 ../.venv/bin/python export_logpmf.py --arm $1 > $W/logs/export_geofon_$1.log 2>&1; echo "$(date -u) export geofon $1 rc=$?" >> $W/logs/export_batch.log; }
ms() { TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 OMP_NUM_THREADS=2 nice ../.venv/bin/python multistation.py --arms $2 --thr 6,7 --reps 1000 --out $R/multistation_$1.json > $W/logs/multistation_$1.log 2>&1; echo "$(date -u) multistation $1 rc=$?" >> $W/logs/ms_batch.log; }
for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll mixdgr_nll; do ex $a; done
ms geofon_s1 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll,mixdgr_nll
for s in 2 3; do
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do ex ${a}_s$s; done
  ms geofon_s$s mix_nll_s$s,mixgr_nll_s$s,eqgr_nll_s$s,eqdgr_nll_s$s
done
echo "$(date -u) geofon_ms done" >> $W/logs/ms_batch.log
