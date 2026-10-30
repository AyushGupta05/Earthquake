#!/bin/bash
# Main host: every 10 minutes, pull finished arms of the 30 Oct SageMaker jobs into the work
# directories (sm_sync.sh) until all of them have ended, then once more.
cd "$(dirname "$0")"
W=/mnt/eew-research/runs/tailwork
L=$W/logs/sm_sync_all.log
E=s3://instance-earthquake-data/sm/jobs
U=s3://instance-earthquake-data-usw2/sm/jobs
sync_all() {
  ./sm_sync.sh $E/tailwork-stead-s23cap-1030/checkpoints/arms /mnt/scratch/stead stead_sm_arms
  ./sm_sync.sh $E/tailwork-chile-cap50x-1030/checkpoints/arms $W/chile chile_arms
  for j in a b2 c d; do ./sm_sync.sh $U/tailwork-inst-$j-usw2/checkpoints/arms $W arms; done
  ./sm_sync.sh $E/tailwork-relabel-mext-1030/checkpoints/arms_mext /mnt/scratch/chile_relabel_mext relabel_mext_sm_arms
  ./sm_sync.sh $E/tailwork-relabel-mwsippl2-1030/checkpoints/arms_mwsippl /mnt/scratch/chile_relabel_mwsippl relabel_mwsippl_sm_arms
  ./sm_sync.sh s3://instance-earthquake-data/tailwork-transfer-20261030/instance/arms $W arms
  ./sm_sync.sh $E/tailwork-mixdgr-stead-chile-1030/checkpoints/arms_stead /mnt/scratch/stead stead_sm_arms
  ./sm_sync.sh $E/tailwork-mixdgr-stead-chile-1030/checkpoints/arms_chile $W/chile chile_arms
  ./sm_sync.sh s3://instance-earthquake-data-use2/sm/jobs/tailwork-mixdgr-instance-use2/checkpoints/arms $W arms
  for j in tailwork-stead-s1-mixgr-use2-g6e2xlarge tailwork-stead-s1-k1-use2-g5xlarge; do
    ./sm_sync.sh s3://instance-earthquake-data-use2/sm/jobs/$j/checkpoints/arms /mnt/scratch/stead stead_sm_arms
  done
}
echo "$(date -u) start" >> $L
while true; do
  sync_all >> $L 2>&1
  [ -f $W/logs/sm_sync_all.stop ] && break
  sleep 600
done
sync_all >> $L 2>&1
echo "$(date -u) sm_sync_all done" >> $L
