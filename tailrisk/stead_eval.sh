#!/bin/bash
# Main host: the pre-registered STEAD evaluations (PREREGISTRATION_STEAD.md with amendments 1-2,
# PREREGISTRATION_STEAD_CAP.md with amendments 1-2). Arms come from this host and from the
# SageMaker jobs (synced by sm_sync_all.sh). Nothing here is tuned on STEAD: arms, thresholds,
# action, reference and statistics are those of the pre-registrations.
S=/mnt/scratch/stead
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/stead_eval.log
export TAILWORK_DIR=$S TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0 CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2
echo "$(date -u) start" >> $L
have() { for a in "$@"; do [ -f $S/arms/$a/fold4.npz ] || return 1; done; }

# classical laws (context only; amendment 1 of the capped pre-registration), CPU, run first
nice ../.venv/bin/python linear_arms.py --laws fwd,fwdR,inv,invR > $W/logs/linear_stead_full.log 2>&1
nice ../.venv/bin/python linear_arms.py --laws fwd,fwdR,inv,invR --cap 5.0 --suffix _cap50 > $W/logs/linear_stead_cap.log 2>&1
echo "$(date -u) classical rc=$?" >> $L

# ---- main test: three-seed ensembles
MAIN="mix_nll eqdgr_nll eqgr_nll mixgr_nll mix_nll_s2 eqdgr_nll_s2 eqgr_nll_s2 mixgr_nll_s2 mix_nll_s3 eqdgr_nll_s3 eqgr_nll_s3 mixgr_nll_s3"
until have $MAIN; do sleep 300; done
echo "$(date -u) main arms present" >> $L
M=mix_nll+mix_nll_s2+mix_nll_s3; E=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
Q=eqgr_nll+eqgr_nll_s2+eqgr_nll_s3; G=mixgr_nll+mixgr_nll_s2+mixgr_nll_s3
ev() { name=$1; shift; TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/stead_eval_$name.json > $W/logs/stead_eval_$name.log 2>&1; echo "$(date -u) stead_eval $name rc=$?" >> $L; }
rob() { name=$1; shift; nice ../.venv/bin/python robust_tail.py "$@" --thr 5,6 --out $R/robust_stead_$name.json > $W/logs/robust_stead_$name.log 2>&1; echo "$(date -u) robust $name rc=$?" >> $L; }
rob ens3 --pairs $E:$M,$Q:$M,$G:$M
ev ens3 --arms $M,$E,$Q --ref $M
ev ens3_prior --arms $M,$G --ref $M
for s in "" _s2 _s3; do ev seed${s:-_s1} --arms mix_nll$s,eqdgr_nll$s,eqgr_nll$s,mixgr_nll$s --ref mix_nll$s; done
# pre-specified subgroups (reported, not part of the decision)
rob ens3_mw --pairs $E:$M,$Q:$M --tail-mask subgroups.npz:mw_tail
rob ens3_noqc --pairs $E:$M,$Q:$M --mask '!gain_qc.npz:suspect'
for reg in Alaska-Aleutians Chile-Argentina Greece-Aegean "New Zealand" California-Nevada; do
  tag=$(echo "$reg" | tr -d ' -' | tr 'A-Z' 'a-z')
  rob ens3_region_$tag --pairs $E:$M,$Q:$M --mask "subgroups.npz:region=$reg"
done
# pooled cross-catalogue analysis (amendment 2)
P=$R/robust_stead_ens3.json
../.venv/bin/python meta_analysis.py --spec INSTANCE:$R/robust_instance.json:5 --spec Chile:$R/robust_chile.json:6 \
  --spec GEOFON:$R/robust_geofon.json:7 --spec STEAD:$P:5 --pair "$E:$M" --out $R/meta_eqdgr.json > $W/logs/meta_eqdgr.log 2>&1
../.venv/bin/python meta_analysis.py --spec INSTANCE:$R/robust_instance.json:5 --spec Chile:$R/robust_chile.json:6 \
  --spec GEOFON:$R/robust_geofon.json:7 --spec STEAD:$P:5 --pair "$Q:$M" --out $R/meta_eqgr.json > $W/logs/meta_eqgr.log 2>&1
echo "$(date -u) meta rc=$?" >> $L
# secondary ablation (seed 1) and classical context
until have eqgr_k1_nll; do sleep 300; done
rob k1 --pairs eqgr_nll:eqgr_k1_nll,eqgr_k1_nll:mix_nll,eqdgr_nll:lin_invR,$E:lin_invR
ev k1_classical --arms mix_nll,eqgr_nll,eqgr_k1_nll,lin_invR,lin_fwdR --ref mix_nll
echo "$(date -u) main done" >> $L

# ---- capped test (seed 1)
CAP="mix_cap50 mix_cap50_aug15 eqgr_cap50 eqdgr_cap50_cond eqgr_k1_cap50 magnet_cap50 mixgr_cap50"
until have $CAP; do sleep 300; done
echo "$(date -u) capped arms present" >> $L
ev cap50 --arms mix_cap50,mix_cap50_aug15,eqgr_cap50,eqdgr_cap50_cond,mixgr_cap50 --ref mix_cap50
ev cap50_base --arms mix_cap50,eqgr_k1_cap50,magnet_cap50,eqdgr_cap50_cond,lin_invR_cap50,lin_fwdR_cap50 --ref mix_cap50
ev cap50_vs_full --arms mix_nll,eqdgr_nll,eqdgr_cap50_cond,eqgr_cap50 --ref mix_nll
rob cap50 --pairs eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50_aug15,eqgr_cap50:mix_cap50_aug15,eqdgr_cap50_cond:eqgr_k1_cap50,eqdgr_cap50_cond:magnet_cap50,mixgr_cap50:mix_cap50,eqdgr_cap50_cond:lin_invR_cap50,eqdgr_cap50_cond:mix_nll
rob cap50_mw --pairs eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50_aug15 --tail-mask subgroups.npz:mw_tail
rob cap50_noqc --pairs eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50 --mask '!gain_qc.npz:suspect'
echo "$(date -u) stead_eval done" >> $L
