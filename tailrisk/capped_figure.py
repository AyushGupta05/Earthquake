"""Figure: predicted vs catalogue magnitude for heads trained below a magnitude cap.

Reads results/capcurve_{instance,chile}.json (cap_curve_data.py) and writes
figures/capped_extrapolation.png. Rows: INSTANCE capped at M4.0, Chile capped at M5.0;
columns: 1, 3, 5 s after the P arrival.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
TEXT, TEXT2, GRID, SURF, BEYOND = '#0b0b0b', '#52514e', '#e9e8e4', '#fcfcfb', '#f1f0ec'
SERIES = [  # (arm key per row, label, color, style); hero first
    ({'instance': 'eqgr_cap40', 'chile': 'eqgr_cap50'}, 'Equivariant head × GR prior, trained below the cap', '#2a78d6', '-'),
    ({'instance': 'mix_cap40', 'chile': 'mix_cap50'}, 'Free mixture (TEAM-LM-style), trained below the cap', '#eb6834', '-'),
    ({'chile': 'mix_cap50_aug15'}, 'Free mixture + amplitude augmentation, trained below the cap', '#1baf7a', '-'),
    ({'instance': 'mix_nll', 'chile': 'mix_nll'}, 'Free mixture trained on all magnitudes (reference)', TEXT2, '--'),
]
ROWS = [('instance', 4.0, 'INSTANCE (Italy): training M < 4.0', (2.4, 6.4)),
        ('chile', 5.0, 'Northern Chile: training M < 5.0', (3.0, 7.0))]

plt.rcParams.update({'font.size': 9, 'axes.edgecolor': TEXT2, 'axes.labelcolor': TEXT, 'xtick.color': TEXT2,
                     'ytick.color': TEXT2, 'axes.linewidth': 0.6, 'font.family': 'DejaVu Sans'})
fig, axes = plt.subplots(2, 3, figsize=(11, 7.2), facecolor=SURF)
handles = {}
for i, (cat, cap, title, (lo, hi)) in enumerate(ROWS):
    d = json.load(open(HERE / 'results' / f'capcurve_{cat}.json'))
    for j, dur in enumerate((1, 3, 5)):
        ax = axes[i, j]; ax.set_facecolor(SURF)
        ax.axvspan(cap, hi, color=BEYOND, zorder=0)
        ax.plot([lo, hi], [lo, hi], color='#b8b7b3', lw=0.9, zorder=1)
        ax.axvline(cap, color=TEXT2, lw=0.8, ls=':', zorder=1)
        if j == 0:
            ax.text(cap + 0.06, lo + 0.12, 'beyond the training range', color=TEXT2, fontsize=7.5, va='bottom')
        for keys, label, color, ls in SERIES:
            if cat not in keys:
                continue
            bins = [b for b in d['arms'][keys[cat]] if b is not None and lo <= b['label_mean'] <= hi]
            x = [b['label_mean'] for b in bins]; y = [b['pred_mean'][j] for b in bins]
            if ls == '-':
                ax.fill_between(x, [b['pred_q25'][j] for b in bins], [b['pred_q75'][j] for b in bins],
                                color=color, alpha=0.10, lw=0, zorder=2)
            h, = ax.plot(x, y, color=color, ls=ls, lw=1.6, marker='o' if ls == '-' else None, ms=3.2,
                         markeredgecolor=SURF, markeredgewidth=0.6, zorder=3)
            handles[label] = h
        ax.set_xlim(lo, hi); ax.set_ylim(lo - 0.6, hi)
        ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        if i == 0:
            ax.set_title(f'{dur} s after the P arrival', color=TEXT, fontsize=10)
        if j == 0:
            ax.set_ylabel(f'{title}\n\npredicted magnitude', color=TEXT)
        if i == 1:
            ax.set_xlabel('catalogue magnitude', color=TEXT)
fig.legend(list(handles.values()), list(handles.keys()), loc='upper center', ncol=2, frameon=False,
           fontsize=8.5, labelcolor=TEXT, bbox_to_anchor=(0.5, 1.0))
fig.text(0.5, 0.005, 'Mean of the posterior median per 0.25-unit label bin (bins with ≥ 2 events); bands: interquartile '
         'range of the records. Grey diagonal: perfect prediction. Out-of-fold, leave-sequence-out, seed 1.',
         ha='center', color=TEXT2, fontsize=7.5)
fig.tight_layout(rect=(0, 0.02, 1, 0.93))
out = HERE / 'figures' / 'capped_extrapolation.png'
fig.savefig(out, dpi=200, facecolor=SURF)
print('wrote', out)
