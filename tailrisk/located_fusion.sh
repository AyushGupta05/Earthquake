#!/bin/bash
# Main host: event-level magnitude versus time when a network location becomes available.
# Each station uses the distance-marginalized head's posterior conditioned on its distance once at
# least four stations of the event have their P (located), the marginal posterior before; fused with
# the rules of fusion_timeline.py (co-located instruments merged). Distance: catalogue (sigma 0) or
# with 26% error (sigma .1). Exploratory.
W=/mnt/eew-research/runs/tailwork
C=$W/chile
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/located_fusion.log
echo "$(date -u) start" >> $L
sfx() { [ $1 = 1 ] && echo "" || echo "_s$1"; }
for s in 1 2 3; do x=$(sfx $s)
  TAILWORK_DIR=$W TAILWORK_MAXMAG=7.5 nice ../.venv/bin/python condr_arms.py --arm eqdgr_nll$x --sigmas 0,0.1 --logpmf > $W/logs/condr_lp_instance$x.log 2>&1
  echo "$(date -u) export instance$x rc=$?" >> $L
  TAILWORK_DIR=$C TAILWORK_MAXMAG=9.5 nice ../.venv/bin/python condr_arms.py --arm eqdgr_nll$x --sigmas 0,0.1 --logpmf > $W/logs/condr_lp_chile$x.log 2>&1
  echo "$(date -u) export chile$x rc=$?" >> $L
done
run() { ds=$1; name=$2; thr=$3; x=$4; shift 4; dir=$W; mm=7.5; [ "$ds" != instance ] && dir=$W/$ds && mm=9.5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$mm OMP_NUM_THREADS=2 nice ../.venv/bin/python fusion_timeline.py --arms mix_nll$x,eqdgr_nll$x \
    --located "eqdgr_nll$x|eqdgr_nll${x}_condR@4,eqdgr_nll$x|eqdgr_nll${x}_condR_s10@4" --thr $thr --reps 1000 --dedupe-stations "$@" \
    --out $R/${name}.json > $W/logs/${name}.log 2>&1
  echo "$(date -u) $name rc=$?" >> $L; }
for s in 1 2 3; do x=$(sfx $s)
  run instance located_timeline_instance_s$s 4,5 "$x"
  run chile located_timeline_chile_s$s 5,6 "$x"
  run chile located_timeline_chile_measured_s$s 5,6 "$x" --timing measured
done
echo "$(date -u) located_fusion done" >> $L
