#!/bin/bash
# Detached driver: pinned prior slope on Chile (beta = -1.79) and GEOFON (beta = -1.32), after the INSTANCE run.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
S=/mnt/scratch
cd "$(dirname "$0")"
until grep -q "bfix_batch done" $W/logs/bfix_batch.log 2>/dev/null; do sleep 300; done
for ds in chile geofon; do
  for a in eqgr_bfix eqdgr_bfix; do mkdir -p $S/${ds}_arms/$a; [ -e $W/$ds/arms/$a ] || ln -s $S/${ds}_arms/$a $W/$ds/arms/$a; done
  mkdir -p $S/${ds}_logpmf; [ -e $W/$ds/logpmf ] || ln -s $S/${ds}_logpmf $W/$ds/logpmf
done
TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_chile_bfix.txt
TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_geofon_bfix.txt
until [ -f $W/chile/arms/eqdgr_bfix/fold4.npz ] && [ -f $W/geofon/arms/eqdgr_bfix/fold4.npz ]; do sleep 120; done; sleep 30
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_bfix,eqdgr_bfix --ref mix_nll --reps 1000 --out $R/chile_eval_bfix.json > $W/logs/chile_eval_bfix.log 2>&1
echo "$(date -u) chile_eval bfix rc=$?" >> $W/logs/bfix_batch.log
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python geofon_eval.py --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_bfix,eqdgr_bfix --ref mix_nll --reps 1000 --out $R/geofon_eval_bfix.json > $W/logs/geofon_eval_bfix.log 2>&1
echo "$(date -u) geofon_eval bfix rc=$?" >> $W/logs/bfix_batch.log
for ds in chile geofon; do
  for a in mix_nll eqgr_bfix eqdgr_bfix; do TAILWORK_DIR=$W/$ds TAILWORK_MAXMAG=9.5 ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_${ds}_$a.log 2>&1; echo "$(date -u) export $ds $a rc=$?" >> $W/logs/bfix_batch.log; done
done
TAILWORK_DIR=$W/chile TAILWORK_MAXMAG=9.5 OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll,eqgr_bfix,eqdgr_bfix --thr 5,6 --reps 1000 --out $R/multistation_chile_bfix.json > $W/logs/multistation_chile_bfix.log 2>&1
echo "$(date -u) multistation chile bfix rc=$?" >> $W/logs/bfix_batch.log
TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5 OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll,eqgr_bfix,eqdgr_bfix --thr 6,7 --reps 1000 --out $R/multistation_geofon_bfix.json > $W/logs/multistation_geofon_bfix.log 2>&1
echo "$(date -u) multistation geofon bfix rc=$?" >> $W/logs/bfix_batch.log
echo "$(date -u) bfix_batch2 done" >> $W/logs/bfix_batch.log
