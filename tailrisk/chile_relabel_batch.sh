#!/bin/bash
# Main host: retrain Chile mix / eqgr / eqdgr on the relabelled caches (independent magnitudes for
# the large events; audit M1), starting after STEAD seed 1 so the pre-registered test is not slowed.
# Runs concurrently with the MagNet queue on the same GPU (small arms, 4 GB each).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/chile_relabel_batch.log
until grep -q "STEAD seed 1 done" $W/logs/main_orchestrator_1030.log 2>/dev/null; do sleep 120; done
for lab in mext mwsippl; do
  D=/mnt/scratch/chile_relabel_$lab
  mkdir -p $D/logs $D/arms
  TAILWORK_DIR=$D TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_chile_relabel.txt
  echo "$(date -u) trained $lab" >> $L
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$D TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll:mix_nll,eqgr_nll:mix_nll --thr 5,6 --tail-mask meta:label_ok --out $R/robust_chile_relabel_$lab.json > $W/logs/robust_chile_relabel_$lab.log 2>&1
  echo "$(date -u) robust $lab rc=$?" >> $L
done
echo "$(date -u) chile_relabel_batch done" >> $L
