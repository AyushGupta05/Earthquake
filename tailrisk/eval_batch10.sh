#!/bin/bash
# Detached driver: INSTANCE held-station test, seeds 2-3 of the distance-marginalized head and the mixture, then three-seed ensembles.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
until [ -f $W/arms/mix_nll_hs_s3/fold4.npz ]; do sleep 300; done; sleep 60
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --station-arm mix_nll_hs --out results/eval_hs_$name.json > $W/logs/eval_hs_$name.log 2>&1; echo "$(date -u) eval hs $name rc=$?" >> $W/logs/eval_batch10.log; }
for s in 2 3; do
  run held_s$s --arms mix_nll_hs_s$s,eqdgr_nll_hs_s$s --ref mix_nll_hs_s$s --station-subset held
  run seen_s$s --arms mix_nll_hs_s$s,eqdgr_nll_hs_s$s --ref mix_nll_hs_s$s --station-subset seen
done
run held_ens3 --arms mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3,eqdgr_nll_hs+eqdgr_nll_hs_s2+eqdgr_nll_hs_s3 --ref mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3 --station-subset held
run seen_ens3 --arms mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3,eqdgr_nll_hs+eqdgr_nll_hs_s2+eqdgr_nll_hs_s3 --ref mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3 --station-subset seen
echo "$(date -u) eval_batch10 done" >> $W/logs/eval_batch10.log
