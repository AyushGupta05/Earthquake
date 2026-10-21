#!/bin/bash
# Detached driver: capacity and training-length checks for the distance-marginalized head, then five-seed ensembles.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --out results/eval_$name.json > $W/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $W/logs/eval_batch12.log; }
until [ -f $W/arms/eqdgr_nll_e20/fold4.npz ]; do sleep 300; done; sleep 60
run w15_3 --arms mix_nll_w15,eqgr_nll_w15,eqdgr_nll_w15 --ref mix_nll_w15
run e20_3 --arms mix_nll_e20,eqgr_nll_e20,eqdgr_nll_e20 --ref mix_nll_e20
until [ -f $W/arms/eqdgr_nll_s5/fold4.npz ]; do sleep 300; done; sleep 60
run ens5 --arms mix_nll+mix_nll_s2+mix_nll_s3+mix_nll_s4+mix_nll_s5,eqgr_nll+eqgr_nll_s2+eqgr_nll_s3+eqgr_nll_s4+eqgr_nll_s5,eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3+eqdgr_nll_s4+eqdgr_nll_s5 --ref mix_nll+mix_nll_s2+mix_nll_s3+mix_nll_s4+mix_nll_s5
run seeds45 --arms mix_nll_s4,eqgr_nll_s4,eqdgr_nll_s4,mix_nll_s5,eqgr_nll_s5 --ref mix_nll_s4
echo "$(date -u) eval_batch12 done" >> $W/logs/eval_batch12.log
