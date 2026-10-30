#!/bin/bash
# Second host, replaces gpu2_followup.sh at 07:55 UTC on 30 Oct (STEAD seeds 2-3 and the capped
# STEAD arms moved to a SageMaker job): after the INSTANCE capped queue, train the kappa=1 arms and
# the capped MagNet arm on INSTANCE and ship each to S3 for the main host.
cd "$(dirname "$0")"
W=/home/ec2-user/tailwork
L=$W/logs/gpu2_followup2.log
B=s3://instance-earthquake-data/tailwork-transfer-20261030
until grep -q "cap_instance_batch done" $W/logs/cap_instance_batch.log 2>/dev/null; do sleep 120; done
echo "$(date -u) start" >> $L
export TAILWORK_DIR=$W
while read -r line; do
  [ -z "$line" ] && continue
  arm=$(echo "$line" | sed -E 's/.*--arm ([^ ]+).*/\1/')
  echo "$line" > $W/q_$arm.txt
  ./run_queue.sh $W/q_$arm.txt
  aws s3 cp $W/arms/$arm $B/instance/arms/$arm --recursive --only-show-errors
  echo "$(date -u) $arm uploaded" >> $L
done < sm_queues/queue_gpu2_inst.txt
echo "$(date -u) gpu2_followup2 done" >> $L
aws s3 cp $L $B/results/gpu2_followup2.log --only-show-errors
