#!/bin/bash
# Detached driver: extrapolation test on Chile. Train only on records with M < 5.0, evaluate every
# record of the held-out folds; tail thresholds 5 / 5.5 / 6 are entirely beyond the training range.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/cap_chile_batch.log
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_chile_cap.txt
ev() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/chile_eval_$name.json > $W/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $L; }
ev cap50 --arms mix_cap50,mixgr_cap50,eqgr_cap50,eqdgr_cap50,eqgr_cap50_bfix,eqdgr_cap50_bfix --ref mix_cap50
ev cap50_aug --arms mix_cap50,mix_cap50_aug05,mix_cap50_aug15,eqdgr_cap50,eqdgr_cap50_bfix --ref mix_cap50
ev cap50_vs_full --arms mix_nll,mix_cap50,eqdgr_cap50,eqdgr_cap50_bfix,eqdgr_nll --ref mix_nll
echo "$(date -u) cap_chile_batch done" >> $L
