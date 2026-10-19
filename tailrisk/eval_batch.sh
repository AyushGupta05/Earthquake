#!/bin/bash
# Sequential evaluation batch (CPU). Logs to $WORK/logs/eval_<name>.log, JSON to $WORK/arms/eval_<name>.json
WORK=/mnt/eew-research/runs/tailwork
cd "$(dirname "$0")"
run() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 nice ../.venv/bin/python evaluate.py "$@" --out $WORK/arms/eval_$name.json > $WORK/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $WORK/logs/eval_batch.log; }
run final_all --arms mix_nll,cat_ce,cat_hubce,cat_aug,cat_lds,mixgr_nll,eqgr_nll --ref mix_nll --reps 1000
run ens2 --arms mix_nll+mix_nll_s2,cat_ce+cat_ce_s2,mixgr_nll+mixgr_nll_s2,eqgr_nll+eqgr_nll_s2 --ref mix_nll+mix_nll_s2 --reps 1000
run explore --arms mix_nll,eqgr_nll,eqtgr_nll,eqdgr_nll --ref mix_nll --reps 1000
run std_val --arms std_mix_nll,std_cat_hubce,std_mixgr_nll,std_eqgr_nll --ref std_mix_nll --split val --reps 1000
run std_test --arms std_mix_nll,std_cat_hubce,std_mixgr_nll,std_eqgr_nll --ref std_mix_nll --split test --reps 1000
