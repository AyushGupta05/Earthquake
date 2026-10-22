#!/bin/bash
# Detached driver: held-station test of the 20-epoch distance-marginalized head and mixture on INSTANCE.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/e20_hs_batch.log
./run_queue.sh queue_e20_hs.txt
for sub in held seen; do
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms mix_nll_e20_hs,eqdgr_nll_e20_hs,mix_nll_hs,eqdgr_nll_hs --ref mix_nll_e20_hs --reps 1000 --station-subset $sub --station-arm mix_nll_hs --out $R/eval_hs_e20_$sub.json > $W/logs/eval_hs_e20_$sub.log 2>&1
  echo "$(date -u) eval hs_e20_$sub rc=$?" >> $L
done
echo "$(date -u) e20_hs_batch done" >> $L
