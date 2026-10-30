#!/bin/bash
# Main host: the pre-registered equal-information test (PREREGISTRATION_EQUALINFO.md). Waits for the
# free distance-mixture arms (SageMaker), conditions both heads on the catalogue distance
# (condr_arms.py, sigma 0 and 0.1), then per catalogue eqdgr|r - mixdgr|r (three-seed ensembles)
# with the robust statistics, pooled over the four catalogues.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
G=$W/geofon
S=/mnt/scratch/stead
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/equalinfo_eval.log
echo "$(date -u) start" >> $L
have() { root=$1; shift; for a in "$@"; do [ -f $root/arms/$a/fold4.npz ] || return 1; done; }
until have $W mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3 && have $C mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3 \
   && have $S mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3 && have $G mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3; do sleep 300; done
echo "$(date -u) arms present" >> $L
link() { root=$1; scr=$2; shift 2; mkdir -p /mnt/scratch/$scr; for a in "$@"; do for t in "" _s10; do
  mkdir -p /mnt/scratch/$scr/${a}_condR$t; [ -e $root/arms/${a}_condR$t ] || ln -s /mnt/scratch/$scr/${a}_condR$t $root/arms/${a}_condR$t; done; done; }
cond() { root=$1; shift; env_extra="$1"; shift; for a in "$@"; do
  env TAILWORK_DIR=$root $env_extra nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_$(basename $root)_$a.log 2>&1
  echo "$(date -u) condR $(basename $root) $a rc=$?" >> $L; done; }
link $W arms mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
link $C chile_arms mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
link $G geofon_arms mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
link $S stead_condr_arms mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
cond $W "TAILWORK_MAXMAG=7.5" mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
cond $C "TAILWORK_MAXMAG=9.5" mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
cond $G "TAILWORK_MAXMAG=9.5" mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
cond $S "TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0" mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
K=eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR; F=mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR
K10=eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10; F10=mixdgr_nll_condR_s10+mixdgr_nll_s2_condR_s10+mixdgr_nll_s3_condR_s10
M=mix_nll+mix_nll_s2+mix_nll_s3
P="$K:$F,$K10:$F10,$F:$M"
rob() { root=$1; name=$2; thr=$3; shift 3; env TAILWORK_DIR=$root "$@" nice ../.venv/bin/python robust_tail.py --pairs $P --thr $thr --out $R/robust_${name}_equalinfo.json > $W/logs/robust_${name}_equalinfo.log 2>&1; echo "$(date -u) robust $name rc=$?" >> $L; }
rob $W instance 4,5 TAILWORK_MAXMAG=7.5
rob $C chile 5,6 TAILWORK_MAXMAG=9.5
rob $G geofon 6,7 TAILWORK_MAXMAG=9.5
rob $S stead 5,6 TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0
SP="--spec INSTANCE:$R/robust_instance_equalinfo.json:5 --spec Chile:$R/robust_chile_equalinfo.json:6 --spec GEOFON:$R/robust_geofon_equalinfo.json:7 --spec STEAD:$R/robust_stead_equalinfo.json:5"
../.venv/bin/python meta_analysis.py $SP --pair "$K:$F" --out $R/meta4_equalinfo.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $SP --pair "$K10:$F10" --out $R/meta4_equalinfo_s10.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $SP --pair "$F:$M" --out $R/meta4_freedist_vs_mix.json > /dev/null 2>&1
echo "$(date -u) equalinfo_eval done" >> $L
