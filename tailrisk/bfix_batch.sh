#!/bin/bash
# Detached driver: GR heads with the prior tail slope pinned to the catalogue b-value (INSTANCE,
# beta = -2.29 nats/unit), single-station evaluation and multi-station fusion with the pinned factor.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
rm -rf $W/chile/logpmf $W/geofon/logpmf        # regenerable scratch from the fusion study
./run_queue.sh queue8.txt
until [ -f $W/arms/eqdgr_bfix/fold4.npz ] && [ -f $W/arms/eqgr_bfix/fold4.npz ]; do sleep 120; done; sleep 30
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 nice ../.venv/bin/python evaluate.py --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_bfix,eqdgr_bfix --ref mix_nll --reps 1000 --out $R/eval_bfix.json > $W/logs/eval_bfix.log 2>&1
echo "$(date -u) eval bfix rc=$?" >> $W/logs/bfix_batch.log
for a in mix_nll eqgr_bfix eqdgr_bfix; do
  ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_$a.log 2>&1; echo "$(date -u) export $a rc=$?" >> $W/logs/bfix_batch.log
done
OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll,eqgr_bfix,eqdgr_bfix --thr 4,5 --reps 1000 --out $R/multistation_instance_bfix.json > $W/logs/multistation_instance_bfix.log 2>&1
echo "$(date -u) multistation bfix rc=$?" >> $W/logs/bfix_batch.log
for a in mix_nll eqgr_bfix eqdgr_bfix; do rm -rf "$W/logpmf/$a"; done
echo "$(date -u) bfix_batch done" >> $W/logs/bfix_batch.log
