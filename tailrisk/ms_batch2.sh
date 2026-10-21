#!/bin/bash
# Detached driver (v2): multi-station study. Waits for the specific export lines, then seed 1 on
# INSTANCE and Chile, seeds 2-3 (exports deleted after use: the results volume is nearly full),
# and finally re-runs the GEOFON seeds with the corrected script.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/export_batch.log
until grep -q "export INSTANCE eqdgr_nll rc=0" $L 2>/dev/null && grep -q "export chile eqdgr_nll rc=0" $L 2>/dev/null; do sleep 60; done
run_ms() { name=$1; dir=$2; thr=$3; arms=$4; maxmag=$5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$maxmag OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms $arms --thr $thr --reps 1000 --out $R/multistation_$name.json > $W/logs/multistation_$name.log 2>&1
  echo "$(date -u) multistation $name rc=$?" >> $W/logs/ms_batch.log; }
run_ms instance_s1 $W 4,5 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll 7.5
run_ms chile_s1 $W/chile 5,6 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll 9.5
for s in 2 3; do
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
    ../.venv/bin/python export_logpmf.py --arm ${a}_s$s > $W/logs/export_${a}_s$s.log 2>&1
    echo "$(date -u) export INSTANCE ${a}_s$s rc=$?" >> $L
  done
  run_ms instance_s$s $W 4,5 mix_nll_s$s,mixgr_nll_s$s,eqgr_nll_s$s,eqdgr_nll_s$s 7.5
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do rm -rf "$W/logpmf/${a}_s$s"; done
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
    TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 ../.venv/bin/python export_logpmf.py --arm ${a}_s$s > $W/logs/export_chile_${a}_s$s.log 2>&1
    echo "$(date -u) export chile ${a}_s$s rc=$?" >> $L
  done
  run_ms chile_s$s $W/chile 5,6 mix_nll_s$s,mixgr_nll_s$s,eqgr_nll_s$s,eqdgr_nll_s$s 9.5
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do rm -rf "$W/chile/logpmf/${a}_s$s"; done
done
until grep -q "geofon_ms done" $W/logs/ms_batch.log; do sleep 60; done
run_ms geofon_s1 $W/geofon 6,7 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll,mixdgr_nll 9.5
run_ms geofon_s2 $W/geofon 6,7 mix_nll_s2,mixgr_nll_s2,eqgr_nll_s2,eqdgr_nll_s2 9.5
run_ms geofon_s3 $W/geofon 6,7 mix_nll_s3,mixgr_nll_s3,eqgr_nll_s3,eqdgr_nll_s3 9.5
echo "$(date -u) ms_batch2 done" >> $W/logs/ms_batch.log
