#!/bin/bash
# Detached driver: INSTANCE held-station test including the distance-marginalized head (4 arms).
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
until [ -f $W/arms/eqdgr_nll_hs/fold4.npz ]; do sleep 120; done; sleep 60
for sub in held seen; do
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms mix_nll_hs,eqgr_nll_hs,mixgr_nll_hs,eqdgr_nll_hs --ref mix_nll_hs --reps 1000 --station-subset $sub --station-arm mix_nll_hs --out results/eval_hs_${sub}4.json > $W/logs/eval_hs_${sub}4.log 2>&1
  echo "$(date -u) eval hs_${sub}4 rc=$?" >> $W/logs/eval_batch9.log
done
