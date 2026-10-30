#!/bin/bash
# Entry point of a SageMaker training job (sm_launch.sh): runs train.py arms from queue.txt in
# parallel, one lane per GPU, pulling lines from a shared queue so lanes stay balanced.
# Channels: code (src.tar.gz = tailrisk/*.py + train_std_full.npy, queue.txt), data (a cache
# directory: meta.npz, wave16.npy, scale.npy, ...). Arms and logs are written under
# /opt/ml/checkpoints, which SageMaker syncs to S3 while the job runs, so finished arms are
# available before the job ends and a restarted job skips them. TAILWORK_* come from the job's
# environment.
set -u
CODE=/opt/ml/input/data/code
DATA=/opt/ml/input/data/data
CK=/opt/ml/checkpoints
W=/opt/ml/work
mkdir -p /opt/ml/src $W $CK/arms $CK/logs
tar -xzf $CODE/src.tar.gz -C /opt/ml/src
for f in $DATA/*; do ln -sf "$f" $W/; done
ln -sfn $CK/arms $W/arms
ln -sfn $CK/logs $W/logs
export TAILWORK_DIR=$W
Q=$W/queue.txt
grep -v '^\s*$' $CODE/queue.txt | grep -v '^#' > $Q
L=$CK/logs/queue.log
NG=$(nvidia-smi -L | wc -l)
echo "$(date -u) start: $NG GPUs, $(wc -l < $Q) arms" >> $L
nvidia-smi >> $L
cd /opt/ml/src/tailrisk
lane() {
  g=$1
  while true; do
    line=$(flock $Q.lock -c "head -n 1 $Q; sed -i '1d' $Q")
    [ -z "$line" ] && break
    arm=$(echo "$line" | sed -E 's/.*--arm ([^ ]+).*/\1/')
    if [ -f "$W/arms/$arm/fold4.npz" ]; then echo "$(date -u) skip $arm" >> $L; continue; fi
    echo "$(date -u) gpu$g start $arm" >> $L
    CUDA_VISIBLE_DEVICES=$g OMP_NUM_THREADS=4 python train.py $line > $W/logs/$arm.log 2>&1
    echo "$(date -u) gpu$g end $arm rc=$?" >> $L
  done
}
for g in $(seq 0 $((NG - 1))); do lane $g & sleep 20; done
wait
echo "$(date -u) all lanes done" >> $L
