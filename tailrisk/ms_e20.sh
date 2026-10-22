#!/bin/bash
# Detached driver: fusion study for the 20-epoch INSTANCE arms (seeds 1-3): exports, multistation, timeline.
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/ms_e20.log
sfx() { [ "$1" = 1 ] && echo "" || echo "_s$1"; }
for s in 1 2 3; do x=$(sfx $s)
  for a in mix_nll_e20 eqdgr_nll_e20; do
    [ -f $W/logpmf/${a}$x/fold4.npz ] || ../.venv/bin/python export_logpmf.py --arm ${a}$x > $W/logs/export_${a}$x.log 2>&1; echo "$(date -u) export ${a}$x rc=$?" >> $L
  done
  OMP_NUM_THREADS=3 nice ../.venv/bin/python multistation.py --arms mix_nll_e20$x,eqdgr_nll_e20$x --thr 4,5 --reps 1000 --out $R/multistation_instance_e20_s$s.json > $W/logs/multistation_instance_e20_s$s.log 2>&1; echo "$(date -u) multistation e20_s$s rc=$?" >> $L
  OMP_NUM_THREADS=3 nice ../.venv/bin/python fusion_timeline.py --arms mix_nll_e20$x,eqdgr_nll_e20$x --thr 4,5 --reps 1000 --out $R/fusion_timeline_instance_e20_s$s.json > $W/logs/fusion_timeline_instance_e20_s$s.log 2>&1; echo "$(date -u) timeline e20_s$s rc=$?" >> $L
done
../.venv/bin/python multistation_summary.py $R/multistation_instance_e20_s1.json $R/multistation_instance_e20_s2.json $R/multistation_instance_e20_s3.json > $R/multistation_summary_instance_e20.md
../.venv/bin/python timeline_summary.py $R/fusion_timeline_instance_e20_s1.json $R/fusion_timeline_instance_e20_s2.json $R/fusion_timeline_instance_e20_s3.json > $R/fusion_timeline_summary_instance_e20.md
echo "$(date -u) ms_e20 done" >> $L
