#!/bin/bash
# Seed-3 and eqdgr replication evaluations (CPU). Waits for each arm's last fold, then
# logs to $WORK/logs/eval_<name>.log, JSON to $WORK/arms/eval_<name>.json
WORK=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
wait_arm() {
  while [ ! -f "$WORK/arms/$1/fold4.npz" ]; do
    pgrep -f run_queue.sh > /dev/null || pgrep -f master.sh > /dev/null || { echo "$(date -u) $1 missing, no runner" >> $WORK/logs/eval_batch.log; exit 1; }
    sleep 60
  done
  sleep 30
}
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice ../.venv/bin/python evaluate.py "$@" --out $WORK/arms/eval_$name.json > $WORK/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $WORK/logs/eval_batch.log; }
M3=mix_nll+mix_nll_s2+mix_nll_s3
C3=cat_ce+cat_ce_s2+cat_ce_s3
MG3=mixgr_nll+mixgr_nll_s2+mixgr_nll_s3
EG3=eqgr_nll+eqgr_nll_s2+eqgr_nll_s3
ED3=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
wait_arm cat_ce_s3
run ens3 --arms $M3,$C3,$MG3,$EG3 --ref $M3 --reps 1000
wait_arm eqdgr_nll_s3
run eqd_s12 --arms mix_nll,eqgr_nll,eqdgr_nll,eqgr_nll_s2,eqdgr_nll_s2 --ref mix_nll --reps 1000
run eqd_s3 --arms mix_nll,eqgr_nll_s3,eqdgr_nll_s3 --ref mix_nll --reps 1000
run eqd_ens3 --arms mix_nll,$EG3,$ED3 --ref mix_nll --reps 1000
run eqd_vs_eqgr3 --arms $EG3,$ED3 --ref $EG3 --reps 1000
run eqd_vs_mix3 --arms $M3,$ED3 --ref $M3 --reps 1000
