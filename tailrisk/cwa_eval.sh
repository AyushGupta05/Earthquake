#!/bin/bash
# Main host: the pre-registered CWA evaluation (PREREGISTRATION_CWA.md, decision rules D1-D4). Waits
# until every arm of sm_queues/queue_cwa.txt is in S3 (trained on any host of the claim pool), syncs
# them here, then runs exactly the pre-registered analyses. Classical laws are context only.
C=/mnt/scratch/cwa
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
P=s3://instance-earthquake-data/sm/cwa
cd "$(dirname "$0")"
L=$W/logs/cwa_eval.log
echo "$(date -u) start" >> $L
ARMS=$(sed -E 's/.*--arm ([^ ]+).*/\1/' sm_queues/queue_cwa.txt)
until for a in $ARMS; do aws s3 ls $P/arms/$a/fold4.npz > /dev/null 2>&1 || exit 1; done; do sleep 300; done
echo "$(date -u) all arms in S3" >> $L
for a in $ARMS; do [ -f $C/arms/$a/fold4.npz ] || aws s3 cp $P/arms/$a $C/arms/$a --recursive --only-show-errors; done
export TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5
M=mix_nll+mix_nll_s2+mix_nll_s3; E=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
Q=eqgr_nll+eqgr_nll_s2+eqgr_nll_s3; G=mixgr_nll+mixgr_nll_s2+mixgr_nll_s3
# distance conditioning (D2), on the GPU
for a in eqdgr_nll eqdgr_nll_s2 eqdgr_nll_s3 mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3; do
  nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_cwa_$a.log 2>&1; echo "$(date -u) condR $a rc=$?" >> $L
done
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
nice ../.venv/bin/python linear_arms.py --laws fwdR,invR > $W/logs/linear_cwa_full.log 2>&1
nice ../.venv/bin/python linear_arms.py --laws fwdR,invR --cap 5.0 --suffix _cap50 > $W/logs/linear_cwa_cap.log 2>&1
echo "$(date -u) classical rc=$?" >> $L
ev() { name=$1; shift; TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/cwa_eval_$name.json > $W/logs/cwa_eval_$name.log 2>&1; echo "$(date -u) cwa_eval $name rc=$?" >> $L; }
rob() { name=$1; shift; nice ../.venv/bin/python robust_tail.py "$@" --thr 5,6 --out $R/robust_cwa_$name.json > $W/logs/robust_cwa_$name.log 2>&1; echo "$(date -u) robust $name rc=$?" >> $L; }
# D1
rob ens3 --pairs $E:$M,$Q:$M,$G:$M
ev ens3 --arms $M,$E,$Q --ref $M
for s in "" _s2 _s3; do ev seed${s:-_s1} --arms mix_nll$s,eqdgr_nll$s,eqgr_nll$s,mixgr_nll$s --ref mix_nll$s; done
# D2
K=eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR; F=mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR
K10=eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10; F10=mixdgr_nll_condR_s10+mixdgr_nll_s2_condR_s10+mixdgr_nll_s3_condR_s10
rob equalinfo --pairs $K:$F,$K10:$F10,$F:$M
rob condR3 --pairs $K:$M,$K10:$M,$K:$E,$K:lin_invR,$K10:lin_invR,$E:lin_invR
# D3
ev cap50 --arms mix_cap50,mix_cap50_aug15,eqgr_cap50,eqdgr_cap50_cond,mixgr_cap50 --ref mix_cap50
ev cap50_base --arms mix_cap50,eqgr_k1_cap50,eqdgr_k1_cap50_cond,eqdgr_kp10_cap50_cond,eqdgr_cap50_cond,lin_invR_cap50 --ref mix_cap50
rob cap50 --pairs eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50_aug15,eqgr_cap50:mix_cap50_aug15,mixgr_cap50:mix_cap50,eqdgr_cap50_cond:eqgr_k1_cap50,eqdgr_cap50_cond:lin_invR_cap50,eqdgr_cap50_cond:mix_nll,eqdgr_k1_cap50_cond:mix_cap50,eqdgr_k1_cap50_cond:mix_cap50_aug15,eqdgr_kp10_cap50_cond:mix_cap50,eqdgr_kp10_cap50_cond:mix_cap50_aug15,eqdgr_kp10_cap50_cond:eqdgr_k1_cap50_cond
# D5: hybrid (slope prior) against kappa = 1 and against the mixture; kappa = 1 against the mixture
Z=eqdgr_k1_nll+eqdgr_k1_nll_s2+eqdgr_k1_nll_s3; H=eqdgr_kp10_nll+eqdgr_kp10_nll_s2+eqdgr_kp10_nll_s3
ZQ=eqgr_k1_nll+eqgr_k1_nll_s2+eqgr_k1_nll_s3; HQ=eqgr_kp10_nll+eqgr_kp10_nll_s2+eqgr_kp10_nll_s3
rob hybrid --pairs $H:$M,$H:$Z,$Z:$M,$H:$E,$HQ:$M,$HQ:$ZQ,$ZQ:$M,$HQ:$Q,eqdgr_kp3_nll:eqdgr_nll,eqdgr_kp3_nll:eqdgr_k1_nll,eqgr_kp3_nll:eqgr_nll
ev hybrid --arms $M,$E,$Z,$H --ref $M
ev hybrid_plain --arms $M,$Q,$ZQ,$HQ --ref $M
# context: kappa = 1 and classical law on full data
rob k1 --pairs eqgr_nll:eqgr_k1_nll,eqgr_k1_nll:mix_nll,$E:lin_invR
# D4: five-catalogue pooling
S5="--spec INSTANCE:$R/robust_instance.json:5 --spec Chile:$R/robust_chile.json:6 --spec GEOFON:$R/robust_geofon.json:7 --spec STEAD:$R/robust_stead_ens3.json:5 --spec CWA:$R/robust_cwa_ens3.json:5"
../.venv/bin/python meta_analysis.py $S5 --pair "$E:$M" --out $R/meta5_eqdgr.json > /dev/null 2>&1
../.venv/bin/python meta_analysis.py $S5 --pair "$Q:$M" --out $R/meta5_eqgr.json > /dev/null 2>&1
S5E="--spec INSTANCE:$R/robust_instance_equalinfo.json:5 --spec Chile:$R/robust_chile_equalinfo.json:6 --spec GEOFON:$R/robust_geofon_equalinfo.json:7 --spec STEAD:$R/robust_stead_equalinfo.json:5 --spec CWA:$R/robust_cwa_equalinfo.json:5"
../.venv/bin/python meta_analysis.py $S5E --pair "$K:$F" --out $R/meta5_equalinfo.json > /dev/null 2>&1
S5K="--spec INSTANCE:$R/robust_instance_condR3.json:5 --spec Chile:$R/robust_chile_condR3.json:6 --spec GEOFON:$R/robust_geofon_condR3.json:7 --spec STEAD:$R/robust_stead_condR3.json:5 --spec CWA:$R/robust_cwa_condR3.json:5"
../.venv/bin/python meta_analysis.py $S5K --pair "$K:$M" --out $R/meta5_condR_vs_mix.json > /dev/null 2>&1
echo "$(date -u) meta rc=$?" >> $L
echo "$(date -u) cwa_eval done" >> $L
