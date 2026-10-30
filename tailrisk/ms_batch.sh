#!/bin/bash
# Detached driver: multi-station study. Seed 1 on INSTANCE and Chile after the first export
# batch, then seeds 2 and 3 (exports are regenerable scratch; each seed is deleted after use
# because the results volume is nearly full).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
until [ "$(grep -c "rc=0" $W/logs/export_batch.log 2>/dev/null)" -ge 8 ]; do sleep 60; done
run_ms() { name=$1; dir=$2; thr=$3; arms=$4; maxmag=$5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$maxmag OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms $arms --thr $thr --reps 1000 --out $R/multistation_$name.json > $W/logs/multistation_$name.log 2>&1
  echo "$(date -u) multistation $name rc=$?" >> $W/logs/ms_batch.log; }
run_ms instance_s1 $W 4,5 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll 7.5
run_ms chile_s1 $W/chile 5,6 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll 9.5
for s in 2 3; do
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
    ../.venv/bin/python export_logpmf.py --arm ${a}_s$s > $W/logs/export_${a}_s$s.log 2>&1
    echo "$(date -u) export INSTANCE ${a}_s$s rc=$?" >> $W/logs/export_batch.log
  done
  run_ms instance_s$s $W 4,5 mix_nll_s$s,mixgr_nll_s$s,eqgr_nll_s$s,eqdgr_nll_s$s 7.5
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do rm -rf "$W/logpmf/${a}_s$s"; done
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
    TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 ../.venv/bin/python export_logpmf.py --arm ${a}_s$s > $W/logs/export_chile_${a}_s$s.log 2>&1
    echo "$(date -u) export chile ${a}_s$s rc=$?" >> $W/logs/export_batch.log
  done
  run_ms chile_s$s $W/chile 5,6 mix_nll_s$s,mixgr_nll_s$s,eqgr_nll_s$s,eqdgr_nll_s$s 9.5
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do rm -rf "$W/chile/logpmf/${a}_s$s"; done
done
echo "$(date -u) ms_batch done" >> $W/logs/ms_batch.log
