"""Cross-dataset summary: Δ(arm − free mixture) per dataset, deadline and arm (median action).

Reads evaluate.py / geofon_eval.py JSONs. Each dataset entry: label=path[:tailkey1,tailkey2].

  python tailrisk/cross_dataset_table.py \
    INSTANCE=results/eval_ens3.json:M>=4_MAE,M>=5_MAE \
    GEOFON=results/geofon_eval_ens3.json:M>=6_MAE,M>=7_MAE \
    Chile=results/chile_eval_ens3.json:M>=5_MAE,M>=6_MAE
"""
import json
import sys
from pathlib import Path


def fmt(v):
    if v is None:
        return 'n/a'
    star = '**' if (v['lo'] > 0 or v['hi'] < 0) else ''
    return f"{star}{v['mean']:+.3f} [{v['lo']:+.3f},{v['hi']:+.3f}]{star}"


def main():
    for spec in sys.argv[1:]:
        label, rest = spec.split('=', 1)
        path, keys = rest.split(':', 1)
        keys = keys.split(',')
        r = json.loads(Path(path).read_text())
        print(f'\n### {label}  (Δ = arm − free-mixture reference, median action; n = {r["n_records"]:,} records; bold = 95% CI excludes zero)\n')
        print('| arm | deadline | Δ bulk MAE | Δ ' + ' | Δ '.join(k.replace('_MAE', '') for k in keys) + ' |')
        print('|---|---|---|' + '---|' * len(keys))
        for arm, by_d in r['vs_ref'].items():
            short = arm.split('+')[0].replace('_nll', '')
            for d, c in by_d.items():
                med = c['median']
                print(f'| {short} | {d} | {fmt(med.get("MAE"))} | ' + ' | '.join(fmt(med.get(k)) for k in keys) + ' |')


if __name__ == '__main__':
    main()
