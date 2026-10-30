#!/bin/bash
# Detached driver: trunk-transfer test on INSTANCE. The equivariant heads on the published MagNet
# CNN+BiLSTM trunk (scale-free input) against the same trunk with amplitude and a free 6-component mixture.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/magnet_trunk_batch.log
while pgrep -f "^/bin/bash ./run_queue.sh queue_chile_cap.txt" > /dev/null; do sleep 60; done
./run_queue.sh queue_magnet_trunk.txt
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms magnet_mix,magnet_eqgr,magnet_eqdgr,magnet_nll,mix_nll,eqgr_nll,eqdgr_nll --ref magnet_mix --reps 1000 --out $R/eval_magnet_trunk.json > $W/logs/eval_magnet_trunk.log 2>&1
echo "$(date -u) eval magnet_trunk rc=$?" >> $L
echo "$(date -u) magnet_trunk_batch done" >> $L
