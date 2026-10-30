#!/bin/bash
# Main host: evaluations of the arms trained on SageMaker and the second host (30 Oct), each run as
# soon as its arms are present: MagNet-trunk transfer, zero-shot cross-catalogue transfer
# (no-static arms), INSTANCE capped three-seed ensembles and the second margin arm.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/followup_evals.log
echo "$(date -u) start" >> $L
have() { root=$1; shift; for a in "$@"; do [ -f $root/arms/$a/fold4.npz ] || return 1; done; }
evi() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --out $R/eval_$name.json > $W/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $L; }
evc() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/chile_eval_$name.json > $W/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $L; }
robi() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=2 TAILWORK_DIR=$W nice ../.venv/bin/python robust_tail.py "$@" --thr 4,5 --out $R/robust_instance_$name.json > $W/logs/robust_instance_$name.log 2>&1; echo "$(date -u) robust $name rc=$?" >> $L; }

# INSTANCE capped: three seeds and the eqgr margin arm
until have $W mix_cap40_s2 mix_cap40_s3 eqgr_cap40_s2 eqgr_cap40_s3 eqdgr_cap40_cond_s2 eqdgr_cap40_cond_s3 eqgr_cap40_m10; do sleep 300; done
M=mix_cap40+mix_cap40_s2+mix_cap40_s3; Q=eqgr_cap40+eqgr_cap40_s2+eqgr_cap40_s3; E=eqdgr_cap40_cond+eqdgr_cap40_cond_s2+eqdgr_cap40_cond_s3
robi cap40_ens3 --pairs $E:$M,$Q:$M,$E:mix_nll+mix_nll_s2+mix_nll_s3,$Q:mix_nll+mix_nll_s2+mix_nll_s3,eqgr_cap40_m10:eqgr_cap40,eqgr_cap40_m10:mix_nll

# MagNet trunk under the equivariant heads (INSTANCE)
until have $W magnet_mix magnet_eqgr magnet_eqdgr; do sleep 300; done
evi magnet_trunk --arms magnet_mix,magnet_eqgr,magnet_eqdgr,magnet_nll,mix_nll --ref magnet_mix
robi magnet_trunk --pairs magnet_eqgr:magnet_mix,magnet_eqdgr:magnet_mix,eqdgr_nll:magnet_eqdgr

# kappa = 1 ablation (INSTANCE; second host)
until have $W eqgr_k1_nll eq_k1_nll eqgr_k1_cap40; do sleep 300; done
evi k1 --arms mix_nll,eqgr_nll,eqgr_k1_nll,eq_k1_nll,eq_nll --ref mix_nll
robi k1 --pairs eqgr_nll:eqgr_k1_nll,eqgr_k1_nll:mix_nll,eqgr_cap40:eqgr_k1_cap40,eqgr_k1_cap40:mix_cap40

# zero-shot transfer between INSTANCE and Chile (no-static arms on both)
until have $W mix_ns eqgr_ns eqdgr_ns && have $C mix_ns eqgr_ns eqdgr_ns; do sleep 300; done
for a in mix_ns eqgr_ns eqdgr_ns; do   # transferred predictions live on /mnt/scratch (results volume nearly full)
  for t in "" _ls; do
    mkdir -p /mnt/scratch/chile_arms/${a}_from_instance$t /mnt/scratch/arms/${a}_from_chile$t
    [ -e $C/arms/${a}_from_instance$t ] || ln -s /mnt/scratch/chile_arms/${a}_from_instance$t $C/arms/${a}_from_instance$t
    [ -e $W/arms/${a}_from_chile$t ] || ln -s /mnt/scratch/arms/${a}_from_chile$t $W/arms/${a}_from_chile$t
  done
done
for a in mix_ns eqgr_ns eqdgr_ns; do
  TAILWORK_DIR=$W TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python transfer_eval.py --arm $a --dst $C --out ${a}_from_instance > $W/logs/transfer_${a}_to_chile.log 2>&1; echo "$(date -u) transfer $a instance->chile rc=$?" >> $L
  TAILWORK_DIR=$C TAILWORK_MAXMAG=7.5 nice ../.venv/bin/python transfer_eval.py --arm $a --dst $W --out ${a}_from_chile > $W/logs/transfer_${a}_to_instance.log 2>&1; echo "$(date -u) transfer $a chile->instance rc=$?" >> $L
done
evc transfer_from_instance --arms mix_ns_from_instance,eqgr_ns_from_instance,eqdgr_ns_from_instance,mix_ns --ref mix_ns_from_instance
evc transfer_from_instance_ls --arms mix_ns_from_instance_ls,eqgr_ns_from_instance_ls,eqdgr_ns_from_instance_ls,mix_ns --ref mix_ns_from_instance_ls
evc native_ns --arms mix_ns,eqgr_ns,eqdgr_ns --ref mix_ns
evi transfer_from_chile --arms mix_ns_from_chile,eqgr_ns_from_chile,eqdgr_ns_from_chile,mix_ns --ref mix_ns_from_chile
evi transfer_from_chile_ls --arms mix_ns_from_chile_ls,eqgr_ns_from_chile_ls,eqdgr_ns_from_chile_ls,mix_ns --ref mix_ns_from_chile_ls
evi native_ns --arms mix_ns,eqgr_ns,eqdgr_ns --ref mix_ns
echo "$(date -u) followup_evals done" >> $L
