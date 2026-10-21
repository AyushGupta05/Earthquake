#!/bin/bash
# Detached driver: time-since-first-P fusion on INSTANCE (seeds 1-3), Chile (seeds 1-3, proxy timing; seed 1 measured timing) and GEOFON (seed 1).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/ft_batch.log
ft() { ds=$1; name=$2; thr=$3; arms=$4; extra=$5; dir=$W; mm=7.5; [ "$ds" != instance ] && dir=$W/$ds && mm=9.5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$mm OMP_NUM_THREADS=3 nice ../.venv/bin/python fusion_timeline.py --arms $arms --thr $thr --reps 1000 $extra --out $R/fusion_timeline_$name.json > $W/logs/fusion_timeline_$name.log 2>&1; echo "$(date -u) fusion_timeline $name rc=$?" >> $L; }
sfx() { [ "$1" = 1 ] && echo "" || echo "_s$1"; }
for s in 1 2 3; do x=$(sfx $s); ft instance instance_s$s 4,5 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x ""; done
for s in 1 2 3; do x=$(sfx $s); ft chile chile_s$s 5,6 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x ""; done
ft chile chile_s1_measured 5,6 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll "--timing measured"
ft geofon geofon_s1 6,7 mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll ""
echo "$(date -u) ft_batch done" >> $L
