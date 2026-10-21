#!/bin/bash
# Detached driver: sensitivity of the histogram-adjusted rule to its smoothing and floor (INSTANCE seed 1).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
until grep -q "ms_batch2 done" $W/logs/ms_batch.log 2>/dev/null; do sleep 120; done
for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do
  ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_${a}_r.log 2>&1; echo "$(date -u) export INSTANCE $a (robustness) rc=$?" >> $W/logs/export_batch.log
done
OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll --thr 4,5 --reps 1000 --out $R/multistation_instance_s1.json > $W/logs/multistation_instance_s1.log 2>&1; echo "$(date -u) multistation instance_s1 (rerun with bias) rc=$?" >> $W/logs/ms_batch.log
for cfg in "0.1 1e-5" "0.5 1e-5" "0.25 1e-4" "0.25 1e-6"; do set -- $cfg
  OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll --thr 4,5 --ks 1,4,all --reps 1000 --hist-sigma $1 --hist-floor $2 --out $R/multistation_instance_s1_hist_s${1}_f${2}.json > $W/logs/multistation_robust_${1}_${2}.log 2>&1
  echo "$(date -u) multistation robust sigma=$1 floor=$2 rc=$?" >> $W/logs/ms_batch.log
done
for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do rm -rf "$W/logpmf/$a"; done
echo "$(date -u) ms_robust done" >> $W/logs/ms_batch.log
