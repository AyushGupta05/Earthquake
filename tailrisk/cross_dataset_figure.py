"""Cross-catalogue summary figure: Δ(arm − free mixture) with 95% intervals at 1, 3 and 5 s.

  python tailrisk/cross_dataset_figure.py --out figures/cross_dataset.png \
     "INSTANCE=results/eval_ens3.json+results/eval_eqdgr_combo.json:M>=5_MAE" \
     "GEOFON=results/geofon_eval_ens3.json+results/geofon_eval_dist_ens3.json:M>=7_MAE" \
     "Chile=results/chile_eval_ens3.json:M>=6_MAE"

One row per catalogue; left panel bulk MAE, right panel the catalogue's top-tail MAE; one bar
group per deadline with the plain (eqgr) and distance-marginalized (eqdgr) heads, three-seed
ensembles against the three-seed mixture ensemble, median action.
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ARMS = ('eqgr', 'eqdgr')
COLORS = {'eqgr': 'C3', 'eqdgr': 'C4'}


def base(arm):
    parts = arm.split('+')
    bases = []
    for p in parts:
        b = re.sub(r'_s\d+$', '', p).replace('_nll', '')
        if b not in bases:
            bases.append(b)
    return '+'.join(bases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('specs', nargs='+')
    args = ap.parse_args()
    fig, axes = plt.subplots(len(args.specs), 2, figsize=(11, 3.2 * len(args.specs)), squeeze=False)
    for r_i, spec in enumerate(args.specs):
        label, rest = spec.split('=', 1)
        paths, tail = rest.split(':', 1)
        vs = {}
        for path in paths.split('+'):
            r = json.loads(Path(path).read_text())
            for arm, by_d in r['vs_ref'].items():
                b = base(arm)
                if b in ARMS and b not in vs:
                    vs[b] = by_d
        for c_i, key in enumerate(('MAE', tail)):
            ax = axes[r_i, c_i]
            x = np.arange(3)
            for a_i, a in enumerate(ARMS):
                if a not in vs:
                    continue
                m = [vs[a][d]['median'][key]['mean'] for d in ('1s', '3s', '5s')]
                lo = [vs[a][d]['median'][key]['lo'] for d in ('1s', '3s', '5s')]
                hi = [vs[a][d]['median'][key]['hi'] for d in ('1s', '3s', '5s')]
                err = [np.subtract(m, lo), np.subtract(hi, m)]
                ax.bar(x + (a_i - 0.5) * 0.36, m, 0.34, yerr=err, capsize=3, color=COLORS[a], label=a)
            ax.axhline(0, color='k', lw=.6)
            ax.set_xticks(x)
            ax.set_xticklabels(['1 s', '3 s', '5 s'])
            ax.set_title(f'{label}: Δ {"bulk" if key == "MAE" else key.replace("_MAE", "")} MAE vs free mixture')
            ax.grid(alpha=.3, axis='y')
            if r_i == 0 and c_i == 0:
                ax.legend(fontsize=8)
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print('wrote', args.out)


if __name__ == '__main__':
    main()
