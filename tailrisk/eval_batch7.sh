#!/bin/bash
# Detached driver: Chile single-station arms (tail thresholds M>=5 / 5.5 / 6).
WORK=/mnt/eew-research/runs/tailwork
C=$WORK/chile
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 180; done; sleep 60; }
crun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --out $C/arms/chile_eval_$name.json > $WORK/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $WORK/logs/eval_batch7.log; }
wait_for $C/arms/eqdgr_nll/fold4.npz
crun seed1 --arms mix_nll,eqgr_nll,mixgr_nll,eqdgr_nll --ref mix_nll --reps 1000
wait_for $C/arms/eqdgr_nll_s3/fold4.npz
crun ens3 --arms mix_nll+mix_nll_s2+mix_nll_s3,eqgr_nll+eqgr_nll_s2+eqgr_nll_s3,mixgr_nll+mixgr_nll_s2+mixgr_nll_s3,eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3 --ref mix_nll+mix_nll_s2+mix_nll_s3 --reps 1000
crun seed2 --arms mix_nll_s2,eqgr_nll_s2,mixgr_nll_s2,eqdgr_nll_s2 --ref mix_nll_s2 --reps 500
crun seed3 --arms mix_nll_s3,eqgr_nll_s3,mixgr_nll_s3,eqdgr_nll_s3 --ref mix_nll_s3 --reps 500
