#!/bin/bash
# Detached driver (main host, after the MagNet trunk test): zero-shot cross-catalogue transfer.
# Catalogue-agnostic arms (no station metadata) on INSTANCE and on Chile, then each predicts the
# other catalogue, raw and label-shift adapted; scored with the destination's folds and bootstrap.
I=/mnt/eew-research/runs/tailwork
C=/mnt/eew-research/runs/tailwork/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
mkdir -p $I/logs $C/logs
L=$I/logs/transfer_batch.log
while pgrep -f "^/bin/bash ./magnet_trunk_batch.sh" > /dev/null; do sleep 60; done
for a in mix_ns eqgr_ns eqdgr_ns; do for d in arms chile_arms; do mkdir -p /mnt/scratch/$d/$a; done; [ -e $I/arms/$a ] || ln -s /mnt/scratch/arms/$a $I/arms/$a; [ -e $C/arms/$a ] || ln -s /mnt/scratch/chile_arms/$a $C/arms/$a; done
TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 ./run_queue.sh queue_ns.txt
TAILWORK_DIR=$I ./run_queue.sh queue_ns.txt
for a in mix_ns eqgr_ns eqdgr_ns; do
  TAILWORK_DIR=$I TAILWORK_MAXMAG=9.5 ../.venv/bin/python transfer_eval.py --arm $a --dst $C --out ${a}_from_instance > $I/logs/transfer_${a}_to_chile.log 2>&1; echo "$(date -u) transfer $a instance->chile rc=$?" >> $L
  TAILWORK_DIR=$C TAILWORK_MAXMAG=7.5 ../.venv/bin/python transfer_eval.py --arm $a --dst $I --out ${a}_from_chile > $I/logs/transfer_${a}_to_instance.log 2>&1; echo "$(date -u) transfer $a chile->instance rc=$?" >> $L
done
evc() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3 TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 TAILWORK_THR=5,5.5,6 nice ../.venv/bin/python geofon_eval.py "$@" --reps 1000 --out $R/chile_eval_$name.json > $I/logs/chile_eval_$name.log 2>&1; echo "$(date -u) chile_eval $name rc=$?" >> $L; }
evi() { name=$1; shift; CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=3 TAILWORK_DIR=$I nice ../.venv/bin/python evaluate.py "$@" --reps 1000 --out $R/eval_$name.json > $I/logs/eval_$name.log 2>&1; echo "$(date -u) eval $name rc=$?" >> $L; }
evc transfer_from_instance --arms mix_ns_from_instance,eqgr_ns_from_instance,eqdgr_ns_from_instance,mix_ns --ref mix_ns_from_instance
evc transfer_from_instance_ls --arms mix_ns_from_instance_ls,eqgr_ns_from_instance_ls,eqdgr_ns_from_instance_ls,mix_ns --ref mix_ns_from_instance_ls
evc native_ns --arms mix_ns,eqgr_ns,eqdgr_ns --ref mix_ns
evi transfer_from_chile --arms mix_ns_from_chile,eqgr_ns_from_chile,eqdgr_ns_from_chile,mix_ns --ref mix_ns_from_chile
evi transfer_from_chile_ls --arms mix_ns_from_chile_ls,eqgr_ns_from_chile_ls,eqdgr_ns_from_chile_ls,mix_ns --ref mix_ns_from_chile_ls
evi native_ns --arms mix_ns,eqgr_ns,eqdgr_ns --ref mix_ns
echo "$(date -u) transfer_batch done" >> $L
