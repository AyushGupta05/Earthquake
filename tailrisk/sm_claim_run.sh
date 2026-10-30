#!/bin/bash
# Entry point of a SageMaker training job that serves a shared S3-claimed queue (claim_runner.py)
# with one lane per GPU, alongside EC2 hosts. Channels: code (src.tar.gz, queue.txt), data (cache).
# CLAIM_PREFIX (s3://bucket/prefix) and TAILWORK_* come from the job environment.
set -u
CODE=/opt/ml/input/data/code
W=/opt/ml/work
mkdir -p /opt/ml/src $W/arms $W/logs
tar -xzf $CODE/src.tar.gz -C /opt/ml/src
for f in /opt/ml/input/data/data/*; do ln -sf "$f" $W/; done
export TAILWORK_DIR=$W
cd /opt/ml/src/tailrisk
NG=$(nvidia-smi -L | wc -l)
for g in $(seq 0 $((NG - 1))); do
  python claim_runner.py --queue $CODE/queue.txt --prefix "$CLAIM_PREFIX" --gpu $g > /opt/ml/output/lane$g.log 2>&1 &
  sleep 30
done
wait
