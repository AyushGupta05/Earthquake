"""Cross-dataset summary: Δ(arm − free mixture) per dataset, deadline and arm (median action).

Reads evaluate.py / geofon_eval.py JSONs. Each dataset entry: label=path[+path...]:tailkey1,tailkey2
(several JSONs for one dataset are concatenated; they must share the reference arm).

  python tailrisk/cross_dataset_table.py \
    INSTANCE=results/eval_ens3.json+results/eval_eqdgr_combo.json:M>=4_MAE,M>=5_MAE \
    GEOFON=results/geofon_eval_ens3.json+results/geofon_eval_dist_ens3.json:M>=6_MAE,M>=7_MAE \
    Chile=results/chile_eval_ens3.json:M>=5_MAE,M>=6_MAE
"""
import json
import re
import sys
from pathlib import Path


def fmt(v):
    if v is None or v.get('mean') is None or v['mean'] != v['mean']:
        return 'n/a'
    star = '**' if (v['lo'] > 0 or v['hi'] < 0) else ''
    return f"{star}{v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]{star}"


def short_name(arm):
    """'mixgr_nll+mixgr_nll_s2+...+eqdgr_nll_s3' -> 'mixgr+eqdgr (avg)'; 'eqgr_nll+eqgr_nll_s2+eqgr_nll_s3' -> 'eqgr'."""
    bases = []
    for a in arm.split('+'):
        b = re.sub(r'_s\d+$', '', a).replace('_nll', '').replace('_ce', '')
        if b not in bases:
            bases.append(b)
    return bases[0] if len(bases) == 1 else '+'.join(bases) + ' (avg)'


def main():
    for spec in sys.argv[1:]:
        label, rest = spec.split('=', 1)
        paths, keys = rest.split(':', 1)
        keys = keys.split(',')
        n = None
        rows = []
        for path in paths.split('+'):
            r = json.loads(Path(path).read_text())
            n = r['n_records']
            for arm, by_d in r['vs_ref'].items():
                for d, c in by_d.items():
                    rows.append((short_name(arm), d, c['median']))
        print(f'\n### {label}  (Δ = arm − free-mixture reference, three-seed ensembles, median action; n = {n:,} records; bold = 95% CI excludes zero)\n')
        print('| arm | deadline | Δ bulk MAE | Δ ' + ' | Δ '.join(k.replace('_MAE', '') for k in keys) + ' |')
        print('|---|---|---|' + '---|' * len(keys))
        for short, d, med in rows:
            print(f'| {short} | {d} | {fmt(med.get("MAE"))} | ' + ' | '.join(fmt(med.get(k)) for k in keys) + ' |')


if __name__ == '__main__':
    main()
