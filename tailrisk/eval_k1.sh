#!/bin/bash
# Main host: evaluate the kappa=1 ablation (Zhang, Zhang & Tian 2021 construction) on INSTANCE,
# full data and capped training, once its arms and the second host's capped arms are present.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/eval_k1.log
until [ -f $W/arms/eq_k1_nll/fold4.npz ] && [ -f $W/arms/mix_cap40/fold4.npz ] && [ -f $W/arms/eqgr_cap40/fold4.npz ] && [ -f $W/arms/eqgr_cap40_bfix/fold4.npz ]; do sleep 300; done; sleep 120
ev() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --out $R/eval_$name.json > $W/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $L; }
ev k1 --arms mix_nll,eqgr_nll,eqgr_k1_nll,eq_k1_nll,eq_nll --ref mix_nll
ev k1_cap40 --arms mix_cap40,eqgr_cap40,eqgr_k1_cap40,eqgr_cap40_bfix --ref mix_cap40
echo "$(date -u) eval_k1 done" >> $L
