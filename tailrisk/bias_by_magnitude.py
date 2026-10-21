"""Bias-by-magnitude figure and table for several datasets from evaluate.py / geofon_eval.py JSONs.

  python tailrisk/bias_by_magnitude.py --out figures/bias_by_magnitude_all.png \
      INSTANCE=results/eval_ens3.json+results/eval_eqdgr_combo.json \
      Chile=results/chile_eval_ens3.json GEOFON=results/geofon_eval_ens3.json+results/geofon_eval_dist_ens3.json

Each JSON stores, per arm and deadline, the mean signed error of the median action in
0.5-unit label bins ('by_magnitude_median'). Panels: one row per dataset, one column per
deadline; lines per arm (ensembles labelled by their base name).
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402


def base(arm):
    parts = arm.split('+')
    bases = []
    for p in parts:
        b = re.sub(r'_s\d+$', '', p).replace('_nll', '').replace('_ce', '')
        if b not in bases:
            bases.append(b)
    return '+'.join(bases)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--table', default=None, help='optional markdown table output')
    ap.add_argument('specs', nargs='+')
    args = ap.parse_args()
    rows = []
    fig, axes = plt.subplots(len(args.specs), 3, figsize=(15, 3.8 * len(args.specs)), squeeze=False)
    for r_i, spec in enumerate(args.specs):
        label, paths = spec.split('=', 1)
        arms = {}
        n_bins = None
        for path in paths.split('+'):
            r = json.loads(Path(path).read_text())
            for arm, by_d in r['arms'].items():
                b = base(arm)
                if b in arms or len(arm.split('+')) > 3:
                    continue
                arms[b] = by_d
        for d_i, d in enumerate(('1s', '3s', '5s')):
            ax = axes[r_i, d_i]
            for c_i, (b, by_d) in enumerate(arms.items()):
                bm = by_d[d]['by_magnitude_median']
                lo = [x['lo'] + 0.25 for x in bm if x['bias_median'] is not None and x['n'] >= 5]
                bias = [x['bias_median'] for x in bm if x['bias_median'] is not None and x['n'] >= 5]
                ax.plot(lo, bias, marker='o', ms=3, label=b, color=f'C{c_i}')
                for x in bm:
                    if x['bias_median'] is not None and x['n'] >= 5:
                        rows.append({'dataset': label, 'deadline': d, 'arm': b, 'bin_lo': x['lo'], 'n': x['n'], 'bias': x['bias_median']})
            ax.axhline(0, color='k', lw=.6)
            ax.set_title(f'{label}, {d[0]} s: mean signed error by label bin (median action)')
            ax.set_xlabel('magnitude bin centre')
            ax.grid(alpha=.3)
            if d_i == 0:
                ax.set_ylabel('estimate − label')
        axes[r_i, 0].legend(fontsize=8)
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print('wrote', args.out)
    if args.table:
        lines = ['| dataset | deadline | arm | bin | n | bias |', '|---|---|---|---|---|---|']
        for x in rows:
            lines.append(f"| {x['dataset']} | {x['deadline']} | {x['arm']} | [{x['bin_lo']:.1f}, {x['bin_lo'] + .5:.1f}) | {x['n']} | {x['bias']:+.3f} |")
        Path(args.table).write_text('# Mean signed error by magnitude bin (median action)\n\n' + '\n'.join(lines) + '\n')
        print('wrote', args.table)


if __name__ == '__main__':
    main()
