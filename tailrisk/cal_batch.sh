#!/bin/bash
# Detached driver: re-export seeds 1-3 of the four main arms on every catalogue (to scratch, kept)
# and re-run the fusion study with the calibrated-tilt rules (all-event objective; GEOFON also
# with the tail objective).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/cal_batch.log
ex() { ds=$1; a=$2; dir=$W; mm=7.5; [ "$ds" != instance ] && dir=$W/$ds && mm=9.5
  if [ -f $dir/logpmf/$a/fold4.npz ]; then echo "$(date -u) export $ds $a exists" >> $L; return; fi
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$mm ../.venv/bin/python export_logpmf.py --arm $a > $W/logs/export_${ds}_$a.log 2>&1; echo "$(date -u) export $ds $a rc=$?" >> $L; }
ms() { ds=$1; name=$2; thr=$3; arms=$4; extra=$5; dir=$W; mm=7.5; [ "$ds" != instance ] && dir=$W/$ds && mm=9.5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$mm OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms $arms --thr $thr --reps 1000 $extra --out $R/multistation_$name.json > $W/logs/multistation_$name.log 2>&1; echo "$(date -u) multistation $name rc=$?" >> $L; }
mkdir -p /mnt/scratch/logpmf /mnt/scratch/chile_logpmf /mnt/scratch/geofon_logpmf
[ -e $W/chile/logpmf ] || ln -s /mnt/scratch/chile_logpmf $W/chile/logpmf
[ -e $W/geofon/logpmf ] || ln -s /mnt/scratch/geofon_logpmf $W/geofon/logpmf
sfx() { [ "$1" = 1 ] && echo "" || echo "_s$1"; }
for s in 1 2 3; do x=$(sfx $s)
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do ex geofon ${a}$x; done
  ms geofon geofon_s$s 6,7 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x ""
  ms geofon geofon_s${s}_caltail 6,7 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x "--cal-on tail"
done
for s in 1 2 3; do x=$(sfx $s)
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do ex chile ${a}$x; done
  ms chile chile_s$s 5,6 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x ""
done
for s in 1 2 3; do x=$(sfx $s)
  for a in mix_nll mixgr_nll eqgr_nll eqdgr_nll; do ex instance ${a}$x; done
  ms instance instance_s$s 4,5 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x ""
done
echo "$(date -u) cal_batch done" >> $L
