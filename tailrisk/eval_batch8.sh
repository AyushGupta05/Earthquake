#!/bin/bash
# Detached driver: Chile held-station test (arms trained with 20% of the 22 stations withheld; 7 stations held).
WORK=/mnt/eew-research/runs/tailwork
C=$WORK/chile
cd "$(dirname "$0")"
wait_for() { until [ -f "$1" ]; do sleep 180; done; sleep 60; }
crun() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --out $C/arms/chile_eval_$name.json > $WORK/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $WORK/logs/eval_batch8.log; }
wait_for $C/arms/eqgr_nll_hs/fold4.npz
crun hs_held --arms mix_nll_hs,eqgr_nll_hs,eqdgr_nll_hs --ref mix_nll_hs --reps 1000 --station-subset held --station-arm mix_nll_hs
crun hs_seen --arms mix_nll_hs,eqgr_nll_hs,eqdgr_nll_hs --ref mix_nll_hs --reps 1000 --station-subset seen --station-arm mix_nll_hs
