#!/bin/bash
# Copy the finished arms (fold4.npz present) of a SageMaker job into a work directory, storing
# them on /mnt/scratch and symlinking them into WORKDIR/arms (the results volume is nearly full).
# Arms already present in WORKDIR/arms are skipped.
#   sm_sync.sh s3://BUCKET/sm/jobs/JOB/checkpoints/arms WORKDIR SCRATCH_SUBDIR
SRC=$1; DST=$2; SCR=/mnt/scratch/$3
mkdir -p $SCR $DST/arms
for a in $(aws s3 ls $SRC/ 2>/dev/null | awk '/PRE/{print $2}' | tr -d /); do
  [ -f $DST/arms/$a/fold4.npz ] && continue
  aws s3 ls $SRC/$a/fold4.npz > /dev/null 2>&1 || continue
  aws s3 cp $SRC/$a $SCR/$a --recursive --only-show-errors
  if [ -d $DST/arms/$a ] && [ ! -L $DST/arms/$a ]; then rmdir $DST/arms/$a 2>/dev/null || { echo "kept existing $DST/arms/$a"; continue; }; fi
  [ -e $DST/arms/$a ] || ln -s $SCR/$a $DST/arms/$a
  echo "$(date -u) synced $a -> $DST/arms"
done
