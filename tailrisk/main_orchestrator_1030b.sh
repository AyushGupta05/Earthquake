#!/bin/bash
# Replaces main_orchestrator_1030.sh at 04:25 UTC on 30 Oct (the original was stopped while its
# STEAD seed-1 queue kept running). STEAD seed 2 of the pre-registered arms moves here from the
# second host, so the three-seed verdict is not serialized behind the INSTANCE capped queue there
# (seed 3 stays on the second host). Same log file and markers as the original.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
L=$W/logs/main_orchestrator_1030.log
while pgrep -f "^/bin/bash ./run_queue.sh queue_stead_s1.txt" > /dev/null; do sleep 60; done
echo "$(date -u) STEAD seed 1 done" >> $L
TAILWORK_DIR=/mnt/scratch/stead TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0 ./run_queue.sh queue_stead_s2.txt
echo "$(date -u) STEAD seed 2 done" >> $L
./magnet_trunk_batch.sh
./transfer_batch.sh
echo "$(date -u) main_orchestrator_1030 done" >> $L
