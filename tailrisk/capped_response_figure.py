"""Figure: amplitude response of capped heads past the training cap.

Reads results/cap_response_{instance,chile}.json and results/cap_response_instance_full.json
(cap_response.py) and writes figures/capped_amplitude_response.png. Records just below the
cap are amplified by 10^delta; the y axis is the mean posterior median.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
TEXT, TEXT2, GRID, SURF, BEYOND = '#0b0b0b', '#52514e', '#e9e8e4', '#fcfcfb', '#f1f0ec'
R = HERE / 'results'
inst = json.load(open(R / 'cap_response_instance.json')); inst_full = json.load(open(R / 'cap_response_instance_full.json'))
chile = json.load(open(R / 'cap_response_chile.json'))
inst['arms'].update(inst_full['arms'])
SERIES = [
    ({'instance': 'eqgr_cap40', 'chile': 'eqgr_cap50'}, 'Equivariant head × GR prior, trained below the cap', '#2a78d6', '-'),
    ({'instance': 'mix_cap40', 'chile': 'mix_cap50'}, 'Free mixture, trained below the cap', '#eb6834', '-'),
    ({'chile': 'mix_cap50_aug15'}, 'Free mixture + amplitude augmentation, trained below the cap', '#1baf7a', '-'),
    ({'instance': 'mix_nll', 'chile': 'mix_nll'}, 'Free mixture trained on all magnitudes (reference)', TEXT2, '--'),
]
ROWS = [('instance', inst, 4.0, 'INSTANCE: records M3.5–4.0,\ntraining M < 4.0'),
        ('chile', chile, 5.0, 'Northern Chile: records M4.5–5.0,\ntraining M < 5.0')]
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': TEXT2, 'xtick.color': TEXT2, 'ytick.color': TEXT2,
                     'axes.linewidth': 0.6, 'font.family': 'DejaVu Sans'})
fig, axes = plt.subplots(2, 3, figsize=(11, 6.6), facecolor=SURF)
handles = {}
for i, (cat, d, cap, title) in enumerate(ROWS):
    deltas = d['deltas']
    for j, dur in enumerate(('1s', '3s', '5s')):
        ax = axes[i, j]; ax.set_facecolor(SURF)
        lo = min(min(d['arms'][k[cat]][dur]['mean_median']) for k, *_ in SERIES if cat in k) - 0.15
        hi = max(max(d['arms'][k[cat]][dur]['mean_median']) for k, *_ in SERIES if cat in k) + 0.15
        ax.axhspan(cap, hi, color=BEYOND, zorder=0)
        ax.axhline(cap, color=TEXT2, lw=0.8, ls=':', zorder=1)
        if j == 0:
            ax.text(0.02, hi - 0.03, 'above the training range', color=TEXT2, fontsize=7.5, va='top')
        for keys, label, color, ls in SERIES:
            if cat not in keys:
                continue
            a = d['arms'][keys[cat]][dur]
            h, = ax.plot(deltas, a['mean_median'], color=color, ls=ls, lw=1.6, marker='o' if ls == '-' else None,
                         ms=3.2, markeredgecolor=SURF, markeredgewidth=0.6, zorder=3)
            handles[label] = h
        ax.set_ylim(lo, hi); ax.set_xlim(-0.05, 2.05)
        ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        if i == 0:
            ax.set_title(f'{dur[0]} s after the P arrival', color=TEXT, fontsize=10)
        if j == 0:
            ax.set_ylabel(f'{title}\n\nmean predicted magnitude', color=TEXT)
        if i == 1:
            ax.set_xlabel('ground motion amplified by 10^x (decades)', color=TEXT)
fig.legend(list(handles.values()), list(handles.keys()), loc='upper center', ncol=2, frameon=False,
           fontsize=8.5, labelcolor=TEXT, bbox_to_anchor=(0.5, 1.0))
fig.text(0.5, 0.005, 'Held-out records just below the cap, waveforms multiplied by 10^x; mean of the posterior median '
         '(up to 2,000 records per fold, five folds). Seed 1.', ha='center', color=TEXT2, fontsize=7.5)
fig.tight_layout(rect=(0, 0.02, 1, 0.92))
out = HERE / 'figures' / 'capped_amplitude_response.png'
fig.savefig(out, dpi=200, facecolor=SURF)
print('wrote', out)
