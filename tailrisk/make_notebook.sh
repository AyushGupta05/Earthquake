#!/bin/bash
# Rebuild and execute tail_risk_study.ipynb (run from tailrisk/ on the host).
cd "$(dirname "$0")"
PY=${PY:-../.venv/bin/python}
$PY build_notebook.py --eval results/eval_final_all.json --diag results/diagnostics_eqgr_nll_mixgr_nll.json \
 --gbm results/gbm_e3ws_summary.json --seedcons results/seedcons_eqgr_nll_vs_mix_nll.json \
 --hs-held results/eval_hs_held4.json --hs-seen results/eval_hs_seen4.json --magnet results/eval_magnet.json \
 --other "GEOFON (3-seed ensembles)=results/geofon_eval_ens3.json,GEOFON distance-marginalized (3-seed ensembles)=results/geofon_eval_dist_ens3.json,Chile (3-seed ensembles)=results/chile_eval_ens3.json,Chile size-matched 6-model averages=results/chile_eval_combo6.json,Chile held stations (7 of 22 withheld)=results/chile_eval_hs_held.json,Chile seen stations (same arms)=results/chile_eval_hs_seen.json" \
 --multistation "INSTANCE=results/multistation_instance_s1.json,Chile=results/multistation_chile_s1.json,GEOFON=results/multistation_geofon_s1.json" > /dev/null \
 && CUDA_VISIBLE_DEVICES= $PY -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1200 tail_risk_study.ipynb > /tmp/nbexec.log 2>&1 \
 && $PY -c "import json; nb=json.load(open('tail_risk_study.ipynb')); c=[x for x in nb['cells'] if x['cell_type']=='code']; e=[o for x in c for o in x.get('outputs',[]) if o.get('output_type')=='error']; print('notebook: code cells', len(c), 'errors', len(e)); assert not e"
