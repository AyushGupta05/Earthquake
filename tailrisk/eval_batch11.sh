#!/bin/bash
# Detached driver: Chile held-station test, seeds 2-3 (distance-marginalized head and mixture) and three-seed ensembles.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
cd "$(dirname "$0")"
until [ -f $C/arms/mix_nll_hs_s3/fold4.npz ]; do sleep 180; done; sleep 60
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --station-arm mix_nll_hs --out results/chile_eval_hs_$name.json > $W/logs/chile_eval_hs_$name.log 2>&1; echo "$(date -u) chile_eval hs $name rc=$?" >> $W/logs/eval_batch11.log; }
for s in 2 3; do
  run held_s$s --arms mix_nll_hs_s$s,eqdgr_nll_hs_s$s --ref mix_nll_hs_s$s --station-subset held
  run seen_s$s --arms mix_nll_hs_s$s,eqdgr_nll_hs_s$s --ref mix_nll_hs_s$s --station-subset seen
done
run held_ens3 --arms mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3,eqdgr_nll_hs+eqdgr_nll_hs_s2+eqdgr_nll_hs_s3 --ref mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3 --station-subset held
run seen_ens3 --arms mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3,eqdgr_nll_hs+eqdgr_nll_hs_s2+eqdgr_nll_hs_s3 --ref mix_nll_hs+mix_nll_hs_s2+mix_nll_hs_s3 --station-subset seen
echo "$(date -u) eval_batch11 done" >> $W/logs/eval_batch11.log
