#!/bin/bash
# Main host, CPU: rerun the fusion studies with one posterior per station and event (audit M4).
W=/mnt/eew-research/runs/tailwork
R=$HOME/Earthquake/tailrisk/results
cd "$(dirname "$0")"
L=$W/logs/ms_dedupe.log
sfx() { [ "$1" = 1 ] && echo "" || echo "_s$1"; }
run() { ds=$1; name=$2; thr=$3; arms=$4; tool=$5; dir=$W; mm=7.5; [ "$ds" != instance ] && dir=$W/$ds && mm=9.5
  TAILWORK_DIR=$dir TAILWORK_MAXMAG=$mm OMP_NUM_THREADS=2 nice -n 15 ../.venv/bin/python $tool --arms $arms --thr $thr --reps 1000 --dedupe-stations --out $R/${name}.json > $W/logs/${name}.log 2>&1
  echo "$(date -u) $name rc=$?" >> $L; }
for s in 1 2 3; do x=$(sfx $s)
  run instance multistation_dedup_instance_s$s 4,5 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x multistation.py
  run chile multistation_dedup_chile_s$s 5,6 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x multistation.py
  run geofon multistation_dedup_geofon_s$s 6,7 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x multistation.py
  run instance fusion_timeline_dedup_instance_s$s 4,5 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x fusion_timeline.py
  run chile fusion_timeline_dedup_chile_s$s 5,6 mix_nll$x,mixgr_nll$x,eqgr_nll$x,eqdgr_nll$x fusion_timeline.py
done
for ds in instance chile geofon; do
  ../.venv/bin/python multistation_summary.py $R/multistation_dedup_${ds}_s1.json $R/multistation_dedup_${ds}_s2.json $R/multistation_dedup_${ds}_s3.json > $R/multistation_summary_dedup_$ds.md
done
for ds in instance chile; do
  ../.venv/bin/python timeline_summary.py $R/fusion_timeline_dedup_${ds}_s1.json $R/fusion_timeline_dedup_${ds}_s2.json $R/fusion_timeline_dedup_${ds}_s3.json > $R/fusion_timeline_summary_dedup_$ds.md
done
echo "$(date -u) ms_dedupe done" >> $L
