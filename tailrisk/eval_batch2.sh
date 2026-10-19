#!/bin/bash
# Detached driver: waits for the queue5 arms and evaluates them (CPU).
WORK=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
wait_for() { until [ -f "$WORK/arms/$1/fold4.npz" ]; do sleep 120; done; sleep 60; }
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice ../.venv/bin/python evaluate.py "$@" --out $WORK/arms/eval_$name.json > $WORK/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $WORK/logs/eval_batch2.log; }
wait_for eqgr_nll_hs
run hs_held --arms mix_nll_hs,eqgr_nll_hs --ref mix_nll_hs --station-subset held --station-arm mix_nll_hs --reps 1000
run hs_seen --arms mix_nll_hs,eqgr_nll_hs --ref mix_nll_hs --station-subset seen --station-arm mix_nll_hs --reps 1000
wait_for magnet_nll
run magnet --arms magnet_nll,mix_nll,cat_ce,eqgr_nll --ref magnet_nll --reps 1000
wait_for mixgr_nll_hs
run hs_held3 --arms mix_nll_hs,mixgr_nll_hs,eqgr_nll_hs --ref mix_nll_hs --station-subset held --station-arm mix_nll_hs --reps 1000
run hs_seen3 --arms mix_nll_hs,mixgr_nll_hs,eqgr_nll_hs --ref mix_nll_hs --station-subset seen --station-arm mix_nll_hs --reps 1000
