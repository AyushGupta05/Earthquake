#!/bin/bash
# Detached driver: distance-marginalized free-mixture ablations on both datasets.
WORK=/mnt/eew-research/runs/tailwork
G=$WORK/geofon
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 180; done; sleep 60; }
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice ../.venv/bin/python evaluate.py "$@" --out $WORK/arms/eval_$name.json > $WORK/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $WORK/logs/eval_batch5.log; }
grun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python geofon_eval.py "$@" --out $G/arms/geofon_eval_$name.json > $WORK/logs/geofon_eval_$name.log 2>&1; echo "$(date -u) geofon_eval $name rc=$?" >> $WORK/logs/eval_batch5.log; }
wait_for $G/arms/mixdgr_nll_s3/fold4.npz
grun dist --arms mix_nll,eqdgr_nll,mixdgr_nll,mixgr_nll --ref mix_nll --reps 1000
grun dist_ens3 --arms mix_nll+mix_nll_s2+mix_nll_s3,eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3,mixdgr_nll+mixdgr_nll_s2+mixdgr_nll_s3 --ref mix_nll+mix_nll_s2+mix_nll_s3 --reps 1000
wait_for $WORK/arms/mixdgr_nll/fold4.npz
run dist --arms mix_nll,mixdgr_nll,eqdgr_nll,eqgr_nll,mixgr_nll --ref mix_nll --reps 1000
