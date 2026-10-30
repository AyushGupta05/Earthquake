#!/bin/bash
# Detached driver for the second GPU host: extrapolation test on INSTANCE. Train only on records
# with M < 4.0 (every M>=4 event is beyond the training range), evaluate all held-out records.
# Results and fold predictions are uploaded to S3 for the main host.
export TAILWORK_DIR=/home/ec2-user/tailwork
W=$TAILWORK_DIR
R=$HOME/Earthquake/tailrisk/results
B=s3://instance-earthquake-data/tailwork-transfer-20261030
cd "$(dirname "$0")"
mkdir -p $W/logs
L=$W/logs/cap_instance_batch.log
./run_queue.sh queue_instance_cap.txt
ev() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3 nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --out $R/eval_$name.json > $W/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $L; aws s3 cp $R/eval_$name.json $B/results/eval_$name.json --only-show-errors; aws s3 cp $W/logs/eval_$name.log $B/results/eval_$name.log --only-show-errors; }
ev cap40 --arms mix_cap40,mixgr_cap40,eqgr_cap40,eqdgr_cap40 --ref mix_cap40
ev cap40_bfix_aug --arms mix_cap40,eqgr_cap40_bfix,eqdgr_cap40_bfix,mix_cap40_aug05,mix_cap40_aug15 --ref mix_cap40
ev cap40_vs_full --arms mix_nll,mix_cap40,eqdgr_cap40,eqdgr_cap40_bfix,eqdgr_nll --ref mix_nll
for a in mix_cap40 mixgr_cap40 eqgr_cap40 eqdgr_cap40 eqgr_cap40_bfix eqdgr_cap40_bfix mix_cap40_aug15 mix_cap40_aug05; do
  aws s3 cp $W/arms/$a $B/instance/arms/$a --recursive --only-show-errors
done
aws s3 cp $W/logs $B/logs_gpu2 --recursive --only-show-errors
echo "$(date -u) cap_instance_batch done" >> $L
aws s3 cp $L $B/results/cap_instance_batch.log --only-show-errors
