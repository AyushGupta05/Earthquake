#!/bin/bash
# Main host CPU: after linear_batch.sh, compare the classical laws with the networks trained on
# all magnitudes (INSTANCE and Chile), with the bootstrap and the small-cluster-robust statistics.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/classical_eval.log
until grep -q "linear_batch done" $W/logs/linear_batch.log 2>/dev/null; do sleep 120; done
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py --arms mix_nll,eqdgr_nll,lin_invR,lin_inv,lin_fwdR --ref mix_nll --reps 1000 --out $R/chile_eval_classical.json > $W/logs/chile_eval_classical.log 2>&1
echo "$(date -u) chile_eval classical rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python evaluate.py --arms mix_nll,eqdgr_nll,lin_invR,lin_inv,lin_fwdR --ref mix_nll --reps 1000 --out $R/eval_classical.json > $W/logs/eval_classical.log 2>&1
echo "$(date -u) eval classical rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll:lin_invR,eqgr_nll:lin_invR,mix_nll:lin_invR --thr 4,5 --out $R/robust_instance_classical.json > $W/logs/robust_instance_classical.log 2>&1
echo "$(date -u) robust instance classical rc=$?" >> $L
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll:lin_invR,eqgr_nll:lin_invR,mix_nll:lin_invR --thr 5,6 --out $R/robust_chile_classical.json > $W/logs/robust_chile_classical.log 2>&1
echo "$(date -u) robust chile classical rc=$?" >> $L
echo "$(date -u) classical_eval done" >> $L
