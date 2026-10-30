"""Figure: per-catalogue and pooled large-event error difference (forest plot).

Reads a meta_analysis.py output (default results/meta_eqdgr.json, falling back to
results/meta3_eqdgr.json) and writes figures/pooled_forest.png. One panel per deadline; each row
is a catalogue's Δ (method ensemble − free-mixture ensemble, record-level MAE at its primary
threshold) with a 95% jackknife interval (t on G − 1 df); the diamond is the random-effects
estimate with its HKSJ interval. Right-hand labels give the sequences favouring the method.

  python forest_figure.py [--meta results/meta_eqdgr.json] [--out figures/pooled_forest.png]
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from scipy import stats

HERE = Path(__file__).resolve().parent
TEXT, TEXT2, GRID, SURF = '#0b0b0b', '#52514e', '#e9e8e4', '#fcfcfb'
MARK, POOL = '#2a78d6', '#0b0b0b'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--meta', default=None)
    ap.add_argument('--out', default=str(HERE / 'figures' / 'pooled_forest.png'))
    args = ap.parse_args()
    path = Path(args.meta) if args.meta else next(p for p in (HERE / 'results' / 'meta_eqdgr.json',
                                                             HERE / 'results' / 'meta3_eqdgr.json') if p.exists())
    rep = json.load(open(path))
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': TEXT2, 'axes.labelcolor': TEXT, 'xtick.color': TEXT2,
                         'ytick.color': TEXT2, 'axes.linewidth': 0.6, 'font.family': 'DejaVu Sans'})
    fig, axes = plt.subplots(1, 3, figsize=(11, 2.4 + 0.42 * len(rep['catalogues'])), facecolor=SURF, sharey=True)
    for ax, t in zip(axes, ('1s', '3s', '5s')):
        dl = rep['deadlines'][t]
        rows = dl['catalogues']
        n = len(rows)
        ax.set_facecolor(SURF)
        ax.axvline(0, color=TEXT2, lw=0.8, zorder=1)
        for i, r in enumerate(rows):
            y = n - i
            half = stats.t.ppf(0.975, r['G'] - 1) * r['se']
            ax.plot([r['delta'] - half, r['delta'] + half], [y, y], color=MARK, lw=1.6, solid_capstyle='round', zorder=2)
            ax.plot(r['delta'], y, 'o', color=MARK, ms=7, markeredgecolor=SURF, markeredgewidth=1.5, zorder=3)
            ax.text(1.02, y, f"{r['clusters_neg']}/{r['clusters_neg'] + r['clusters_pos']}", transform=ax.get_yaxis_transform(),
                    va='center', ha='left', fontsize=7.5, color=TEXT2)
        p = dl['tail']
        lo, hi = p.get('hksj_ci', p['random_ci'])
        ax.add_patch(Polygon([[lo, 0], [p['random'], 0.22], [hi, 0], [p['random'], -0.22]], closed=True,
                             facecolor=POOL, edgecolor=POOL, zorder=3))
        ax.text(1.02, 0, f"{dl['clusters_neg']}/{dl['clusters_neg'] + dl['clusters_pos']}", transform=ax.get_yaxis_transform(),
                va='center', ha='left', fontsize=7.5, color=TEXT)
        ax.set_yticks(list(range(n, 0, -1)) + [0])
        ax.set_yticklabels([f"{r['catalogue']} M≥{r['thr']:g}" for r in rows] + ['pooled (random effects, HKSJ)'])
        ax.set_ylim(-0.8, n + 0.8)
        ax.grid(axis='x', color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right', 'left'):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis='y', length=0)
        ax.set_title(f'{t[:-1]} s after the P arrival', color=TEXT, fontsize=10)
        ax.set_xlabel('Δ large-event MAE (method − free mixture)', color=TEXT, fontsize=8.5)
    fig.text(0.5, 0.01, 'Three-seed ensembles, median action. Bars: 95% delete-one-cluster jackknife intervals; '
             'right: sequences (GK clusters) favouring the method / sequences with large events.',
             ha='center', fontsize=7.5, color=TEXT2)
    fig.tight_layout(rect=(0, 0.06, 0.97, 1))
    Path(args.out).parent.mkdir(exist_ok=True)
    fig.savefig(args.out, dpi=200, facecolor=SURF)
    print('wrote', args.out, 'from', path.name)


if __name__ == '__main__':
    main()
