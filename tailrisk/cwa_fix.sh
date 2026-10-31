#!/bin/bash
# Main host: redo the parts of cwa_eval.sh that failed when /mnt/scratch filled up overnight
# (one distance-conditioned arm, the classical laws, and everything downstream: D2, D3, the
# equal-information and known-distance five-catalogue pooling, the verdict). The pre-registered
# analyses are unchanged; only the disk-full failure is repaired.
C=/mnt/scratch/cwa
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd ~/Earthquake/tailrisk
L=$W/logs/cwa_fix.log
echo "$(date -u) start" >> $L
rm -rf /mnt/scratch/logpmf /mnt/scratch/chile_logpmf      # regenerable log-posterior exports
rm -f $C/linfeat.npz                                      # truncated by the full disk
df -h /mnt/scratch | tail -1 >> $L
export TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5
for a in eqdgr_nll eqdgr_nll_s2 eqdgr_nll_s3 mixdgr_nll mixdgr_nll_s2 mixdgr_nll_s3; do
  if [ ! -f $C/arms/${a}_condR/fold4.npz ] || [ ! -f $C/arms/${a}_condR_s10/fold4.npz ]; then
    nice ../.venv/bin/python condr_arms.py --arm $a --sigmas 0,0.1 > $W/logs/condr_cwa_$a.log 2>&1; echo "$(date -u) condR $a rc=$?" >> $L
  fi
done
export CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3
nice ../.venv/bin/python linear_arms.py --laws fwdR,invR > $W/logs/linear_cwa_full.log 2>&1; echo "$(date -u) linear full rc=$?" >> $L
nice ../.venv/bin/python linear_arms.py --laws fwdR,invR --cap 5.0 --suffix _cap50 > $W/logs/linear_cwa_cap.log 2>&1; echo "$(date -u) linear cap rc=$?" >> $L
M=mix_nll+mix_nll_s2+mix_nll_s3; E=eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3
K=eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR; F=mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR
K10=eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10; F10=mixdgr_nll_condR_s10+mixdgr_nll_s2_condR_s10+mixdgr_nll_s3_condR_s10
ev() { name=$1; shift; TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/cwa_eval_$name.json > $W/logs/cwa_eval_$name.log 2>&1; echo "$(date -u) cwa_eval $name rc=$?" >> $L; }
rob() { name=$1; shift; nice ../.venv/bin/python robust_tail.py "$@" --thr 5,6 --out $R/robust_cwa_$name.json > $W/logs/robust_cwa_$name.log 2>&1; echo "$(date -u) robust $name rc=$?" >> $L; }
rob equalinfo --pairs $K:$F,$K10:$F10,$F:$M
rob condR3 --pairs $K:$M,$K10:$M,$K:$E,$K:lin_invR,$K10:lin_invR,$E:lin_invR
ev cap50_base --arms mix_cap50,eqgr_k1_cap50,eqdgr_k1_cap50_cond,eqdgr_kp10_cap50_cond,eqdgr_cap50_cond,lin_invR_cap50 --ref mix_cap50
rob cap50 --pairs eqdgr_cap50_cond:mix_cap50,eqgr_cap50:mix_cap50,eqdgr_cap50_cond:mix_cap50_aug15,eqgr_cap50:mix_cap50_aug15,mixgr_cap50:mix_cap50,eqdgr_cap50_cond:eqgr_k1_cap50,eqdgr_cap50_cond:lin_invR_cap50,eqdgr_cap50_cond:mix_nll,eqdgr_k1_cap50_cond:mix_cap50,eqdgr_k1_cap50_cond:mix_cap50_aug15,eqdgr_kp10_cap50_cond:mix_cap50,eqdgr_kp10_cap50_cond:mix_cap50_aug15,eqdgr_kp10_cap50_cond:eqdgr_k1_cap50_cond
rob k1 --pairs eqgr_nll:eqgr_k1_nll,eqgr_k1_nll:mix_nll,$E:lin_invR
S5E="--spec INSTANCE:$R/robust_instance_equalinfo.json:5 --spec Chile:$R/robust_chile_equalinfo.json:6 --spec GEOFON:$R/robust_geofon_equalinfo.json:7 --spec STEAD:$R/robust_stead_equalinfo.json:5 --spec CWA:$R/robust_cwa_equalinfo.json:5"
../.venv/bin/python meta_analysis.py $S5E --pair "$K:$F" --out $R/meta5_equalinfo.json > /dev/null 2>&1
S5K="--spec INSTANCE:$R/robust_instance_condR3.json:5 --spec Chile:$R/robust_chile_condR3.json:6 --spec GEOFON:$R/robust_geofon_condR3.json:7 --spec STEAD:$R/robust_stead_condR3.json:5 --spec CWA:$R/robust_cwa_condR3.json:5"
../.venv/bin/python meta_analysis.py $S5K --pair "$K:$M" --out $R/meta5_condR_vs_mix.json > /dev/null 2>&1
echo "$(date -u) meta rc=$?" >> $L
../.venv/bin/python cwa_verdict.py > $W/logs/cwa_verdict.log 2>&1; echo "$(date -u) verdict rc=$?" >> $L
git add results/cwa_eval_*.json results/robust_cwa_*.json results/robust_cwa_*.md results/meta5_*.json results/meta5_*.md results/CWA_VERDICT.md 2>/dev/null
git commit -q -m "CWA: D2, D3 and the pooled known-distance analyses, recomputed after the overnight disk-full failure (unattended)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push -q origin main
echo "$(date -u) committed rc=$?" >> $L
echo "$(date -u) cwa_fix done" >> $L
