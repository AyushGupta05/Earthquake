#!/bin/bash
# Detached driver: evaluates the queue6 capacity/epoch pairs and the GEOFON arms as they complete.
WORK=/mnt/eew-research/runs/tailwork
G=$WORK/geofon
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 120; done; sleep 60; }
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice ../.venv/bin/python evaluate.py "$@" --out $WORK/arms/eval_$name.json > $WORK/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $WORK/logs/eval_batch3.log; }
grun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python geofon_eval.py "$@" --out $G/arms/geofon_eval_$name.json > $WORK/logs/geofon_eval_$name.log 2>&1; echo "$(date -u) geofon_eval $name rc=$?" >> $WORK/logs/eval_batch3.log; }
# GEOFON first (small arms, early)
wait_for $G/arms/mixgr_nll/fold4.npz
grun seed1 --arms mix_nll,eqgr_nll,mixgr_nll --ref mix_nll --reps 1000
wait_for $G/arms/mixgr_nll_s3/fold4.npz
grun ens3 --arms mix_nll+mix_nll_s2+mix_nll_s3,eqgr_nll+eqgr_nll_s2+eqgr_nll_s3,mixgr_nll+mixgr_nll_s2+mixgr_nll_s3 --ref mix_nll+mix_nll_s2+mix_nll_s3 --reps 1000
grun seeds23 --arms mix_nll_s2,eqgr_nll_s2,mix_nll_s3,eqgr_nll_s3 --ref mix_nll_s2 --reps 500
# capacity / epochs (INSTANCE)
wait_for $WORK/arms/eqgr_nll_e20/fold4.npz
run e20 --arms mix_nll_e20,eqgr_nll_e20,mix_nll,eqgr_nll --ref mix_nll_e20 --reps 1000
wait_for $WORK/arms/eqgr_nll_w15/fold4.npz
run w15 --arms mix_nll_w15,eqgr_nll_w15,mix_nll,eqgr_nll --ref mix_nll_w15 --reps 1000
