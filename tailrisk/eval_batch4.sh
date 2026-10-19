#!/bin/bash
# Detached driver: evaluates the GEOFON follow-up arms (kappa>=0, distance-aware, two-scale).
WORK=/mnt/eew-research/runs/tailwork
G=$WORK/geofon
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 120; done; sleep 60; }
grun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python geofon_eval.py "$@" --out $G/arms/geofon_eval_$name.json > $WORK/logs/geofon_eval_$name.log 2>&1; echo "$(date -u) geofon_eval $name rc=$?" >> $WORK/logs/eval_batch4.log; }
wait_for $G/arms/eqtgr_nll/fold4.npz
grun variants --arms mix_nll,eqgr_nll,eqgr_k0,eqdgr_nll,eqtgr_nll --ref mix_nll --reps 1000
wait_for $G/arms/eqgr_k0_s3/fold4.npz
grun k0_ens3 --arms mix_nll+mix_nll_s2+mix_nll_s3,mixgr_nll+mixgr_nll_s2+mixgr_nll_s3,eqgr_k0+eqgr_k0_s2+eqgr_k0_s3 --ref mix_nll+mix_nll_s2+mix_nll_s3 --reps 1000
