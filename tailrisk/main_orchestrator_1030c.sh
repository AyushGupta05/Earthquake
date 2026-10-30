#!/bin/bash
# Replaces main_orchestrator_1030b.sh at 07:50 UTC on 30 Oct. STEAD seeds 2-3, the MagNet-trunk,
# kappa=1, no-static and remaining INSTANCE capped arms, and the relabelled-Chile retraining moved
# to SageMaker jobs and the second host (sm_queues/); their evaluations run when the arms are
# synced back. This keeps the seed-1 marker the waiting evaluators use.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
L=$W/logs/main_orchestrator_1030.log
while pgrep -f "^/bin/bash ./run_queue.sh queue_stead_s1.txt" > /dev/null; do sleep 60; done
echo "$(date -u) STEAD seed 1 done" >> $L
echo "$(date -u) main_orchestrator_1030c done" >> $L
