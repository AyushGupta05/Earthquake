#!/bin/bash
# Main host, concurrent with STEAD: replaces capcond_batch.sh after the 30 Oct audit found that
# labels in [cap - 0.05, cap) round into the masked cap bin (Chile has 84 such training rows).
# All Chile capped arms are retrained with the bin-consistent filter (--cap-filter bin, now the
# default; suffix "b"), then evaluated with the robust statistics. INSTANCE has no such labels,
# so its capped rows are unchanged; its two additions follow.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/capcond_batch_v2.log
echo "$(date -u) start (waiting for the diagnostic eqdgr_cap50_cond run)" >> $L
while pgrep -f "arm eqdgr_cap50_cond " > /dev/null; do sleep 60; done
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_chile_cap50b.txt
echo "$(date -u) chile trained" >> $L
ev() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/chile_eval_$name.json > $W/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $L; }
ev cap50b --arms mix_cap50b,mixgr_cap50b,mix_cap50b_aug15,eqgr_cap50b,eqdgr_cap50b_cond --ref mix_cap50b
ev cap50b_base --arms mix_cap50b,magnet_cap50b,eqgr_k1_cap50b,eqgr_cap50b,eqdgr_cap50b_cond --ref mix_cap50b
ev cap50b_vs_full --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_cap50b,eqdgr_cap50b_cond --ref mix_nll
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py \
  --pairs eqgr_cap50b:mix_cap50b,eqdgr_cap50b_cond:mix_cap50b,eqgr_cap50b:mix_cap50b_aug15,eqdgr_cap50b_cond:mix_cap50b_aug15,eqgr_cap50b:magnet_cap50b,eqgr_cap50b:eqgr_k1_cap50b,eqgr_cap50b:mix_nll,eqdgr_cap50b_cond:mix_nll \
  --thr 5,6 --out $R/robust_chile_cap50b.json > $W/logs/robust_chile_cap50b.log 2>&1
echo "$(date -u) robust chile rc=$?" >> $L
./run_queue.sh queue_instance_capcond.txt
echo "$(date -u) instance trained" >> $L
echo "$(date -u) capcond_batch_v2 done" >> $L
