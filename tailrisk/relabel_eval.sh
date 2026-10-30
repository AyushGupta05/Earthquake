#!/bin/bash
# Main host: evaluation of the Chile arms retrained on the relabelled caches (independent magnitudes
# M_EXT / MW_SIPPL for the large events; audit M1), trained on SageMaker and synced here. Replaces the
# evaluation parts of chile_relabel_batch.sh and relabel_cap_eval.sh. Tail records are restricted to
# those with an independent label (meta:label_ok).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/relabel_eval.log
echo "$(date -u) start" >> $L
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_MAXMAG=9.5
for lab in mext mwsippl; do
  D=/mnt/scratch/chile_relabel_$lab
  until for a in mix_nll eqdgr_nll eqgr_nll mix_cap50 eqgr_cap50 eqdgr_cap50_cond; do [ -f $D/arms/$a/fold4.npz ] || exit 1; done; do sleep 300; done
  echo "$(date -u) $lab arms present" >> $L
  TAILWORK_DIR=$D nice ../.venv/bin/python robust_tail.py --pairs eqdgr_nll:mix_nll,eqgr_nll:mix_nll --thr 5,6 --tail-mask meta:label_ok --out $R/robust_chile_relabel_$lab.json > $W/logs/robust_chile_relabel_$lab.log 2>&1
  echo "$(date -u) robust $lab rc=$?" >> $L
  TAILWORK_DIR=$D nice ../.venv/bin/python robust_tail.py --pairs eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_nll,eqdgr_cap50_cond:mix_nll,eqdgr_nll:mix_nll \
    --thr 5,6 --tail-mask meta:label_ok --out $R/robust_chile_relabel_cap50_$lab.json > $W/logs/robust_chile_relabel_cap50_$lab.log 2>&1
  echo "$(date -u) robust cap $lab rc=$?" >> $L
done
echo "$(date -u) relabel_eval done" >> $L
