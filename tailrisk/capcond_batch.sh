#!/bin/bash
# Main host, concurrent with STEAD on the same GPU: capped-training follow-ups.
# (1) Chile capped at M5.0: the distance-marginalized head retrained with the conditional cap
#     (models.joint_log_prob; the joint cap leaked mass above the cap in 4/5 folds), plus two
#     existing-method baselines trained the same way: kappa = 1 (Zhang, Zhang & Tian 2021) and
#     the published MagNet architecture. Evaluated against every capped arm and the full-data arms,
#     with the small-cluster-robust statistics.
# (2) INSTANCE capped at M4.0: the same two additions (evaluated once the second host's arms are in).
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/capcond_batch.log
echo "$(date -u) start" >> $L
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_chile_capcond.txt
echo "$(date -u) chile trained" >> $L
ev() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/chile_eval_$name.json > $W/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $L; }
ev capcond --arms mix_cap50,mixgr_cap50,mix_cap50_aug15,magnet_cap50,eqgr_k1_cap50,eqgr_cap50,eqdgr_cap50_cond,eqdgr_cap50_bfix_cond --ref mix_cap50
ev capcond_vs_full --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_cap50,eqdgr_cap50_cond,eqdgr_cap50_bfix_cond --ref mix_nll
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py \
  --pairs eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50_aug15,eqdgr_cap50_cond:mix_cap50_aug15,eqgr_cap50:magnet_cap50,eqgr_cap50:eqgr_k1_cap50,eqgr_cap50:mix_nll,eqdgr_cap50_cond:mix_nll \
  --thr 5,6 --out $R/robust_chile_cap50.json > $W/logs/robust_chile_cap50.log 2>&1
echo "$(date -u) robust chile rc=$?" >> $L
./run_queue.sh queue_instance_capcond.txt
echo "$(date -u) instance trained" >> $L
echo "$(date -u) capcond_batch done" >> $L
