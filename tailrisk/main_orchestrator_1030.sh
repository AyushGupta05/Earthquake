#!/bin/bash
# Main host, 30 Oct: after the Chile capped queue, train STEAD seed 1 (pre-registered arms),
# then the MagNet trunk test, then the cross-catalogue transfer test.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
L=$W/logs/main_orchestrator_1030.log
while pgrep -f "^/bin/bash ./run_queue.sh queue_chile_cap.txt" > /dev/null; do sleep 60; done
echo "$(date -u) start STEAD seed 1" >> $L
mkdir -p /mnt/scratch/stead/logs
TAILWORK_DIR=/mnt/scratch/stead TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0 ./run_queue.sh queue_stead_s1.txt
echo "$(date -u) STEAD seed 1 done" >> $L
./magnet_trunk_batch.sh
./transfer_batch.sh
echo "$(date -u) main_orchestrator_1030 done" >> $L
