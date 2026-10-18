#!/bin/bash
# Usage: run_queue.sh QUEUE_FILE   (each line: arm-args for train.py)
# Runs arms sequentially on the single GPU; logs to $WORK/logs/<arm>.log
WORK=/mnt/eew-research/runs/tailwork
mkdir -p $WORK/logs
cd "$(dirname "$0")"
while read -r line; do
  [ -z "$line" ] && continue
  case "$line" in \#*) continue;; esac
  arm=$(echo "$line" | sed -E 's/.*--arm ([^ ]+).*/\1/')
  if [ -f "$WORK/arms/$arm/fold4.npz" ] || [ -f "$WORK/arms/$arm/std.npz" ]; then echo "skip $arm"; continue; fi
  echo "$(date -u) start $arm" >> $WORK/logs/queue.log
  ../.venv/bin/python train.py $line > $WORK/logs/$arm.log 2>&1
  echo "$(date -u) end $arm rc=$?" >> $WORK/logs/queue.log
done < "$1"
