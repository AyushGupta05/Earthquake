#!/bin/bash
# GPU2 CPU: capped INSTANCE networks (M<4.0) against the classical laws fitted under the same cap.
export TAILWORK_DIR=/home/ec2-user/tailwork CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
W=$TAILWORK_DIR; R=$HOME/Earthquake/tailrisk/results; B=s3://instance-earthquake-data/tailwork-transfer-20261030
cd ~/Earthquake/tailrisk
L=$W/logs/cap40_classical.log
nice ../.venv/bin/python evaluate.py --arms mix_cap40,eqgr_cap40,eqdgr_cap40,eqgr_k1_cap40,lin_invR_cap40,lin_fwdR_cap40,lin_inv_cap40 --ref mix_cap40 --reps 1000 --out $R/eval_cap40_classical.json > $W/logs/eval_cap40_classical.log 2>&1
echo "$(date -u) eval rc=$?" >> $L
nice ../.venv/bin/python robust_tail.py --pairs eqdgr_cap40:lin_invR_cap40,eqgr_cap40:lin_invR_cap40,mix_cap40:lin_invR_cap40,eqgr_cap40:eqgr_k1_cap40,eqdgr_cap40:eqgr_k1_cap40,lin_invR_cap40:lin_invR --thr 4,5 --out $R/robust_instance_cap40_classical.json > $W/logs/robust_instance_cap40_classical.log 2>&1
echo "$(date -u) robust rc=$?" >> $L
for f in eval_cap40_classical.json robust_instance_cap40_classical.json robust_instance_cap40_classical.md; do aws s3 cp $R/$f $B/results/$f --only-show-errors; done
aws s3 cp $W/logs/eval_cap40_classical.log $B/results/ --only-show-errors
echo "$(date -u) cap40_classical done" >> $L
aws s3 cp $L $B/results/cap40_classical.log --only-show-errors
