#!/bin/bash
# Detached driver: GEOFON distance heads with the distance grid extended to 2,500 km.
WORK=/mnt/eew-research/runs/tailwork
G=$WORK/geofon
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 180; done; sleep 60; }
grun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.4 nice ../.venv/bin/python geofon_eval.py "$@" --out $G/arms/geofon_eval_$name.json > $WORK/logs/geofon_eval_$name.log 2>&1; echo "$(date -u) geofon_eval $name rc=$?" >> $WORK/logs/eval_batch6.log; }
wait_for $G/arms/mixdgr_r34_s3/fold4.npz
grun r34 --arms mix_nll,eqdgr_nll,eqdgr_r34,mixdgr_r34 --ref mix_nll --reps 1000
grun r34_ens3 --arms mix_nll+mix_nll_s2+mix_nll_s3,eqdgr_r34+eqdgr_r34_s2+eqdgr_r34_s3,mixdgr_r34+mixdgr_r34_s2+mixdgr_r34_s3 --ref mix_nll+mix_nll_s2+mix_nll_s3 --reps 1000
