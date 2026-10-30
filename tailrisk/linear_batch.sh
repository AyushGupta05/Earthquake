#!/bin/bash
# Main host CPU: classical log-amplitude laws as arms (linear_arms.py), full data and capped.
W=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
L=$W/logs/linear_batch.log
echo "$(date -u) start" >> $L
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3
TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python linear_arms.py > $W/logs/linear_chile_full.log 2>&1; echo "$(date -u) chile full rc=$?" >> $L
TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python linear_arms.py --cap 5.0 --suffix _cap50b > $W/logs/linear_chile_cap.log 2>&1; echo "$(date -u) chile cap rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python linear_arms.py > $W/logs/linear_instance_full.log 2>&1; echo "$(date -u) instance full rc=$?" >> $L
TAILWORK_DIR=$W nice ../.venv/bin/python linear_arms.py --cap 4.0 --suffix _cap40 > $W/logs/linear_instance_cap.log 2>&1; echo "$(date -u) instance cap rc=$?" >> $L
echo "$(date -u) linear_batch done" >> $L
