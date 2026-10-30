#!/bin/bash
# Second GPU host: after the INSTANCE capped queue, train STEAD seeds 2-3 of the pre-registered
# arms and ship each finished arm to S3 for evaluation on the main host.
cd "$(dirname "$0")"
L=/home/ec2-user/tailwork/logs/gpu2_followup.log
B=s3://instance-earthquake-data/tailwork-stead-20261030
until grep -q "cap_instance_batch done" /home/ec2-user/tailwork/logs/cap_instance_batch.log 2>/dev/null; do sleep 120; done
echo "$(date -u) start" >> $L
mkdir -p /home/ec2-user/stead/logs
aws s3 cp $B /home/ec2-user/stead --recursive --exclude "arms/*" --exclude "inventory/*" --only-show-errors
echo "$(date -u) STEAD downloaded" >> $L
export TAILWORK_DIR=/home/ec2-user/stead TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0
while read -r line; do
  [ -z "$line" ] && continue
  arm=$(echo "$line" | sed -E 's/.*--arm ([^ ]+).*/\1/')
  echo "$line" > /home/ec2-user/stead/q_$arm.txt
  ./run_queue.sh /home/ec2-user/stead/q_$arm.txt
  aws s3 cp /home/ec2-user/stead/arms/$arm $B/arms/$arm --recursive --only-show-errors
  aws s3 cp /home/ec2-user/stead/logs/$arm.log $B/logs/$arm.log --only-show-errors
  echo "$(date -u) $arm uploaded" >> $L
done < queue_stead_s23.txt
echo "$(date -u) gpu2_followup done" >> $L
aws s3 cp $L $B/logs/gpu2_followup.log --only-show-errors
