#!/bin/bash
# Main host: distance-informed inference with the trained distance-marginalized heads (no
# retraining; condr_arms.py), then the like-for-like comparison with the classical inverse law
# fitted with catalogue distance (lin_invR) on INSTANCE and Chile. Output arms live on
# /mnt/scratch (symlinked into the work directories; the results volume is full).
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/condr_batch.log
echo "$(date -u) start" >> $L
for a in eqdgr_nll mixdgr_nll; do
  TAILWORK_DIR=$W nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1,0.2 > $W/logs/condr_$a.log 2>&1
  echo "$(date -u) instance $a rc=$?" >> $L
done
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python condr_arms.py --arm eqdgr_nll --sigmas 0,0.1,0.2 > $W/logs/condr_chile_eqdgr_nll.log 2>&1
echo "$(date -u) chile eqdgr_nll rc=$?" >> $L
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
TAILWORK_DIR=$W nice ../.venv/bin/python evaluate.py --arms lin_invR,eqdgr_nll,eqdgr_nll_condR,eqdgr_nll_condR_s10,eqdgr_nll_condR_s20 --ref lin_invR --reps 1000 --out $R/eval_condR.json > $W/logs/eval_condR.log 2>&1
echo "$(date -u) eval condR rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python evaluate.py --arms lin_invR,mixdgr_nll,mixdgr_nll_condR,eqdgr_nll_condR --ref lin_invR --reps 1000 --out $R/eval_condR_free.json > $W/logs/eval_condR_free.log 2>&1
echo "$(date -u) eval condR_free rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll_condR:lin_invR,eqdgr_nll_condR_s10:lin_invR,eqdgr_nll_condR_s20:lin_invR,eqdgr_nll_condR:eqdgr_nll,eqdgr_nll_condR:mixdgr_nll_condR,mixdgr_nll_condR:lin_invR --thr 4,5 --out $R/robust_instance_condR.json > $W/logs/robust_instance_condR.log 2>&1
echo "$(date -u) robust instance condR rc=$?" >> $L
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py --arms lin_invR,eqdgr_nll,eqdgr_nll_condR,eqdgr_nll_condR_s10,eqdgr_nll_condR_s20,mix_nll --ref lin_invR --reps 1000 --out $R/chile_eval_condR.json > $W/logs/chile_eval_condR.log 2>&1
echo "$(date -u) chile_eval condR rc=$?" >> $L
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll_condR:lin_invR,eqdgr_nll_condR_s10:lin_invR,eqdgr_nll_condR_s20:lin_invR,eqdgr_nll_condR:eqdgr_nll --thr 5,6 --out $R/robust_chile_condR.json > $W/logs/robust_chile_condR.log 2>&1
echo "$(date -u) robust chile condR rc=$?" >> $L
echo "$(date -u) condr_batch done" >> $L
