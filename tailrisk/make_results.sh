#!/bin/bash
# Regenerate RESULTS.md from the evaluation JSONs (run from tailrisk/ on the host).
cd "$(dirname "$0")"
PY=${PY:-../.venv/bin/python}
ARGS=(
 "INSTANCE, single seeds, main arms and baselines=results/eval_final_all.json:M>=4,M>=5"
 "INSTANCE, three-seed ensembles=results/eval_ens3.json:M>=4,M>=5"
 "INSTANCE, distance-marginalized head, three-seed ensembles=results/eval_eqdgr_combo.json:M>=4,M>=5"
 "INSTANCE, size-matched six-model averages=results/eval_eqdgr_combo6.json:M>=4,M>=5"
 "INSTANCE, distance-marginalized free mixture and distance variants (single seeds)=results/eval_dist.json:M>=4,M>=5"
 "INSTANCE, pinned prior slope (beta −2.29), single seeds=results/eval_bfix.json:M>=4,M>=5"
 "INSTANCE, held stations (20% withheld; records at held stations; four arms, seed 1)=results/eval_hs_held4.json:M>=4,M>=5"
 "INSTANCE, held stations (records at seen stations; four arms, seed 1)=results/eval_hs_seen4.json:M>=4,M>=5"
 "INSTANCE, held stations, three-seed ensembles (records at held stations)=results/eval_hs_held_ens3.json:M>=4,M>=5"
 "INSTANCE, held stations, three-seed ensembles (records at seen stations)=results/eval_hs_seen_ens3.json:M>=4,M>=5"
 "INSTANCE, MagNet-style control=results/eval_magnet.json:M>=4,M>=5"
 "INSTANCE, 1.5x trunk width (three heads)=results/eval_w15_3.json:M>=4,M>=5"
 "INSTANCE, 20 epochs (three heads)=results/eval_e20_3.json:M>=4,M>=5"
 "INSTANCE, 20 epochs, three-seed ensembles (reference: 20-epoch mixture ensemble)=results/eval_e20_ens3.json:M>=4,M>=5"
 "INSTANCE, 20 epochs, seeds 2 and 3 (reference: 20-epoch mixture seed 2)=results/eval_e20_seeds23.json:M>=4,M>=5"
 "INSTANCE, five-seed ensembles=results/eval_ens5.json:M>=4,M>=5"
 "INSTANCE, seeds 4 and 5 (single seeds; reference mixture seed 4)=results/eval_seeds45.json:M>=4,M>=5"
 "GEOFON regional subset, three-seed ensembles=results/geofon_eval_ens3.json:M>=6,M>=7"
 "GEOFON, distance-marginalized heads, three-seed ensembles=results/geofon_eval_dist_ens3.json:M>=6,M>=7"
 "GEOFON, pinned prior slope (beta −1.32), single seeds=results/geofon_eval_bfix.json:M>=6,M>=7"
 "GEOFON, 20 epochs (reference: 20-epoch mixture)=results/geofon_eval_e20.json:M>=6,M>=7"
 "Northern Chile, three-seed ensembles=results/chile_eval_ens3.json:M>=5,M>=6"
 "Northern Chile, size-matched six-model averages=results/chile_eval_combo6.json:M>=5,M>=6"
 "Northern Chile, pinned prior slope (beta −1.79), single seeds=results/chile_eval_bfix.json:M>=5,M>=6"
 "Northern Chile, 20 epochs (reference: 20-epoch mixture)=results/chile_eval_e20.json:M>=5,M>=6"
 "Northern Chile, held stations (7 of 22 withheld; records at held stations; seed 1)=results/chile_eval_hs_held.json:M>=5,M>=6"
 "Northern Chile, held stations (records at seen stations; seed 1)=results/chile_eval_hs_seen.json:M>=5,M>=6"
 "STEAD (pre-registered fourth catalogue), three-seed ensembles=results/stead_eval_ens3.json:M>=5,M>=6"
 "STEAD, capped at M5.0 (pre-registered), seed 1=results/stead_eval_cap50.json:M>=5,M>=6"
 "STEAD, capped at M5.0, baselines and classical law=results/stead_eval_cap50_base.json:M>=5,M>=6"
 "INSTANCE, classical amplitude laws as arms=results/eval_classical.json:M>=4,M>=5"
 "INSTANCE, conditioned on a known distance (seed 1)=results/eval_condR.json:M>=4,M>=5"
 "INSTANCE, capped at M4.0=results/eval_cap40.json:M>=4,M>=5"
 "INSTANCE, capped at M4.0, augmentation and pinned slope=results/eval_cap40_bfix_aug.json:M>=4,M>=5"
 "Northern Chile, classical amplitude laws as arms=results/chile_eval_classical.json:M>=5,M>=6"
 "Northern Chile, conditioned on a known distance (seed 1)=results/chile_eval_condR.json:M>=5,M>=6"
 "GEOFON, capped at M6.0 (pre-registered), seed 1=results/geofon_eval_cap60.json:M>=6,M>=7"
 "GEOFON, capped at M6.0, three-seed ensembles=results/geofon_eval_cap60_ens.json:M>=6,M>=7"
 "GEOFON, capped at M6.0, baselines and classical law=results/geofon_eval_cap60_base.json:M>=6,M>=7"
)
if [ -f results/chile_eval_hs_held_ens3.json ]; then
  ARGS+=("Northern Chile, held stations, three-seed ensembles (records at held stations)=results/chile_eval_hs_held_ens3.json:M>=5,M>=6")
  ARGS+=("Northern Chile, held stations, three-seed ensembles (records at seen stations)=results/chile_eval_hs_seen_ens3.json:M>=5,M>=6")
fi
$PY results_tables.py "${ARGS[@]}" --include=results/multistation_summary_instance.md --include=results/multistation_summary_chile.md --include=results/multistation_summary_geofon.md --include=results/multistation_summary_geofon_caltail.md --include=results/fusion_timeline_summary_instance.md --include=results/fusion_timeline_summary_chile.md --include=results/fusion_timeline_summary_chile_measured.md --include=results/fusion_timeline_summary_geofon.md --include=results/multistation_summary_instance_e20.md --include=results/fusion_timeline_summary_instance_e20.md --include=results/robust_stead_ens3.md --include=results/meta_eqdgr.md --include=results/robust_stead_cap50.md --include=results/meta4_condR_vs_mix.md > RESULTS.md
echo "RESULTS.md: $(wc -l < RESULTS.md) lines, $(grep -c '^## ' RESULTS.md) sections"
