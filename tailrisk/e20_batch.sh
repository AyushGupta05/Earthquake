#!/bin/bash
# Detached driver: 20-epoch training-length check on Chile and GEOFON (mixture and distance-marginalized head), then seeds 2-3 of the INSTANCE 20-epoch arms with three-seed-ensemble evaluation.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/e20_batch.log
TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_e20_other.txt
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py --arms mix_nll_e20,eqdgr_nll_e20,mix_nll,eqdgr_nll --ref mix_nll_e20 --reps 1000 --out $R/chile_eval_e20.json > $W/logs/chile_eval_e20.log 2>&1; echo "$(date -u) chile_eval e20 rc=$?" >> $L
TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_e20_other.txt
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python geofon_eval.py --arms mix_nll_e20,eqdgr_nll_e20,mix_nll,eqdgr_nll --ref mix_nll_e20 --reps 1000 --out $R/geofon_eval_e20.json > $W/logs/geofon_eval_e20.log 2>&1; echo "$(date -u) geofon_eval e20 rc=$?" >> $L
./run_queue.sh queue_e20_seeds.txt
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms mix_nll_e20+mix_nll_e20_s2+mix_nll_e20_s3,eqdgr_nll_e20+eqdgr_nll_e20_s2+eqdgr_nll_e20_s3,mix_nll+mix_nll_s2+mix_nll_s3,eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3 --ref mix_nll_e20+mix_nll_e20_s2+mix_nll_e20_s3 --reps 1000 --out $R/eval_e20_ens3.json > $W/logs/eval_e20_ens3.log 2>&1; echo "$(date -u) eval e20_ens3 rc=$?" >> $L
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms mix_nll_e20_s2,eqdgr_nll_e20_s2,mix_nll_e20_s3,eqdgr_nll_e20_s3 --ref mix_nll_e20_s2 --reps 1000 --out $R/eval_e20_seeds23.json > $W/logs/eval_e20_seeds23.log 2>&1; echo "$(date -u) eval e20_seeds23 rc=$?" >> $L
echo "$(date -u) e20_batch done" >> $L
