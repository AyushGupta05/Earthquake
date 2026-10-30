#!/bin/bash
# Main host: after chile_relabel_batch.sh, score the capped arms trained on the relabelled Chile
# caches (no event with an independent-label M >= 5 in training) against the independent labels
# of the large events only (tail records restricted to label_ok), with the robust statistics.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/relabel_cap_eval.log
until grep -q "chile_relabel_batch done" $W/logs/chile_relabel_batch.log 2>/dev/null; do sleep 300; done
for lab in mext mwsippl; do
  D=/mnt/scratch/chile_relabel_$lab
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3 TAILWORK_DIR=$D TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py \
    --pairs eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_nll,eqdgr_cap50_cond:mix_nll,eqdgr_nll:mix_nll \
    --thr 5,6 --tail-mask meta:label_ok --out $R/robust_chile_relabel_cap50_$lab.json > $W/logs/robust_chile_relabel_cap50_$lab.log 2>&1
  echo "$(date -u) robust cap $lab rc=$?" >> $L
done
echo "$(date -u) relabel_cap_eval done" >> $L
