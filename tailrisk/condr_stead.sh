#!/bin/bash
# Main host: distance-informed inference on STEAD (three seeds of eqdgr_nll), then the three-seed
# comparisons and the pooled four-catalogue analysis of "head given distance" against the free
# mixture and against the classical inverse law given the same distance.
S=/mnt/scratch/stead
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/condr_stead.log
export TAILWORK_DIR=$S TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0
echo "$(date -u) start" >> $L
for a in eqdgr_nll eqdgr_nll_s2 eqdgr_nll_s3; do
  nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_stead_$a.log 2>&1
  echo "$(date -u) $a rc=$?" >> $L
done
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
M=mix_nll+mix_nll_s2+mix_nll_s3; E=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
K=eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR; K10=eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10
nice ../.venv/bin/python robust_tail.py --pairs $K:$M,$K10:$M,$K:$E,$K:lin_invR,$K10:lin_invR,$E:lin_invR --thr 5,6 --out $R/robust_stead_condR3.json > $W/logs/robust_stead_condR3.log 2>&1
echo "$(date -u) robust rc=$?" >> $L
SP="--spec INSTANCE:$R/robust_instance_condR3.json:5 --spec Chile:$R/robust_chile_condR3.json:6 --spec GEOFON:$R/robust_geofon_condR3.json:7 --spec STEAD:$R/robust_stead_condR3.json:5"
../.venv/bin/python meta_analysis.py $SP --pair "$K:$M" --out $R/meta4_condR_vs_mix.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $SP --pair "$K:lin_invR" --out $R/meta4_condR_vs_invR.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $SP --pair "$K10:$M" --out $R/meta4_condR10_vs_mix.json > /dev/null 2>&1
echo "$(date -u) condr_stead done" >> $L
