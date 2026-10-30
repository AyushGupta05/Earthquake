#!/bin/bash
# Main host, after condr_batch.sh: distance-informed inference for seeds 2-3 (INSTANCE, Chile)
# and GEOFON seeds 1-3, then three-seed comparisons with the robust statistics against the
# free-mixture ensemble, the marginal head and the oracle-distance classical law, and the pooled
# analysis of "head with distance" vs "classical law with the same distance".
W=/mnt/eew-research/runs/tailwork
C=$W/chile
G=$W/geofon
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/condr_batch2.log
echo "$(date -u) start" >> $L
until tail -n 1 $W/logs/condr_batch.log | grep -q "condr_batch done"; do sleep 60; done
link() { root=$1; scr=$2; shift 2; for a in "$@"; do for t in "" _s10 _s20; do mkdir -p /mnt/scratch/$scr/${a}_condR$t; [ -e $root/arms/${a}_condR$t ] || ln -s /mnt/scratch/$scr/${a}_condR$t $root/arms/${a}_condR$t; done; done; }
link $W arms eqdgr_nll_s2 eqdgr_nll_s3
link $C chile_arms eqdgr_nll_s2 eqdgr_nll_s3
mkdir -p /mnt/scratch/geofon_arms; link $G geofon_arms eqdgr_nll eqdgr_nll_s2 eqdgr_nll_s3
for a in eqdgr_nll_s2 eqdgr_nll_s3; do
  TAILWORK_DIR=$W nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_$a.log 2>&1; echo "$(date -u) instance $a rc=$?" >> $L
  TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_chile_$a.log 2>&1; echo "$(date -u) chile $a rc=$?" >> $L
done
for a in eqdgr_nll eqdgr_nll_s2 eqdgr_nll_s3; do
  TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1,0.2 > $W/logs/condr_geofon_$a.log 2>&1; echo "$(date -u) geofon $a rc=$?" >> $L
done
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
M=mix_nll+mix_nll_s2+mix_nll_s3; E=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
K=eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR; K10=eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10
PAIRS="$K:$M,$K10:$M,$K:$E,$K:lin_invR,$K10:lin_invR,$E:lin_invR"
TAILWORK_DIR=$W nice ../.venv/bin/python robust_tail.py --pairs $PAIRS --thr 4,5 --out $R/robust_instance_condR3.json > $W/logs/robust_instance_condR3.log 2>&1
echo "$(date -u) robust instance rc=$?" >> $L
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py --pairs $PAIRS --thr 5,6 --out $R/robust_chile_condR3.json > $W/logs/robust_chile_condR3.log 2>&1
echo "$(date -u) robust chile rc=$?" >> $L
until grep -q "classical rc" $W/logs/geofon_cap_batch.log 2>/dev/null; do sleep 120; done
TAILWORK_DIR=$G TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python robust_tail.py --pairs $PAIRS --thr 6,7 --fp-low 5.0 --fp-cut 5.95 --out $R/robust_geofon_condR3.json > $W/logs/robust_geofon_condR3.log 2>&1
echo "$(date -u) robust geofon rc=$?" >> $L
S="--spec INSTANCE:$R/robust_instance_condR3.json:5 --spec Chile:$R/robust_chile_condR3.json:6 --spec GEOFON:$R/robust_geofon_condR3.json:7"
../.venv/bin/python meta_analysis.py $S --pair "$K:lin_invR" --out $R/meta3_condR_vs_invR.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $S --pair "$K:$M" --out $R/meta3_condR_vs_mix.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $S --pair "$K10:lin_invR" --out $R/meta3_condR10_vs_invR.json > /dev/null 2>&1
echo "$(date -u) meta rc=$?" >> $L
echo "$(date -u) condr_batch2 done" >> $L
