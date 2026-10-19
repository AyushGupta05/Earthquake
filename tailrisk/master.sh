#!/bin/bash
# Usage: master.sh WAIT_PID QUEUE_FILE [QUEUE_FILE ...]
# Waits for WAIT_PID to exit, then runs each queue sequentially on the GPU.
cd "$(dirname "$0")"
while kill -0 "$1" 2>/dev/null; do sleep 30; done
shift
for q in "$@"; do ./run_queue.sh "$q"; done
