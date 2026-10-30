#!/bin/bash
# Main host: pre-registered capped-training test on GEOFON (PREREGISTRATION_GEOFON_CAP.md).
# GEOFON arms take minutes, so they share the GPU with the running queues. Arms live on
# /mnt/scratch (the results volume is nearly full).
W=/mnt/eew-research/runs/tailwork
G=$W/geofon
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/geofon_cap_batch.log
echo "$(date -u) start" >> $L
until tail -n 1 $W/logs/condr_batch.log | grep -q "condr_batch done"; do sleep 60; done
mkdir -p /mnt/scratch/geofon_arms
for a in $(sed -E 's/.*--arm ([^ ]+).*/\1/' queue_geofon_cap60.txt) lin_fwd_cap60 lin_fwdR_cap60 lin_inv_cap60 lin_invR_cap60 lin_fwd lin_fwdR lin_inv lin_invR; do
  mkdir -p /mnt/scratch/geofon_arms/$a; [ -e $G/arms/$a ] || ln -s /mnt/scratch/geofon_arms/$a $G/arms/$a
done
TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_geofon_cap60.txt
echo "$(date -u) trained" >> $L
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5
nice ../.venv/bin/python linear_arms.py --laws fwd,fwdR,inv,invR --cap 6.0 --suffix _cap60 > $W/logs/linear_geofon_cap.log 2>&1
nice ../.venv/bin/python linear_arms.py --laws fwd,fwdR,inv,invR > $W/logs/linear_geofon_full.log 2>&1
echo "$(date -u) classical rc=$?" >> $L
ev() { name=$1; shift; TAILWORK_THR=6,6.5,7 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/geofon_eval_$name.json > $W/logs/geofon_eval_$name.log 2>&1; echo "$(date -u) geofon_eval $name rc=$?" >> $L; }
ev cap60 --arms mix_cap60,mix_cap60_aug15,eqgr_cap60,eqdgr_cap60_cond,mixgr_cap60 --ref mix_cap60
ev cap60_base --arms mix_cap60,eqgr_k1_cap60,magnet_cap60,lin_invR_cap60,lin_fwdR_cap60,eqdgr_cap60_cond --ref mix_cap60
ev cap60_ens --arms mix_cap60+mix_cap60_s2+mix_cap60_s3,eqgr_cap60+eqgr_cap60_s2+eqgr_cap60_s3,eqdgr_cap60_cond+eqdgr_cap60_cond_s2+eqdgr_cap60_cond_s3,mix_nll+mix_nll_s2+mix_nll_s3 --ref mix_cap60+mix_cap60_s2+mix_cap60_s3
ev classical --arms mix_nll,eqdgr_nll,lin_invR,lin_inv,lin_fwdR --ref mix_nll
E="+eqdgr_cap60_cond_s2+eqdgr_cap60_cond_s3"; Q="+eqgr_cap60_s2+eqgr_cap60_s3"; M="+mix_cap60_s2+mix_cap60_s3"
nice ../.venv/bin/python robust_tail.py --pairs eqdgr_cap60_cond$E:mix_cap60$M,eqgr_cap60$Q:mix_cap60$M,eqdgr_cap60_cond:mix_cap60_aug15,eqgr_cap60:mix_cap60_aug15,eqdgr_cap60_cond:eqgr_k1_cap60,eqdgr_cap60_cond:magnet_cap60,eqdgr_cap60_cond:lin_invR_cap60,eqdgr_cap60_cond$E:mix_nll+mix_nll_s2+mix_nll_s3 \
  --thr 6,7 --fp-low 5.0 --fp-cut 5.95 --out $R/robust_geofon_cap60.json > $W/logs/robust_geofon_cap60.log 2>&1
echo "$(date -u) robust rc=$?" >> $L
echo "$(date -u) geofon_cap_batch done" >> $L
