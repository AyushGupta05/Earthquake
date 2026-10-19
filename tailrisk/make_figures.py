"""Figures from an evaluate.py report (and optional diagnostics report).

  python tailrisk/make_figures.py --eval <eval.json> [--diag <diagnostics.json>] --out tailrisk/figures
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

COLORS = ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B3', '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD']


def frontier_plot(rep, out, tail_key='M>=4_MAE', name='frontier'):
    arms = list(rep['arms'])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, d in zip(axes, ('1s', '3s', '5s')):
        for i, a in enumerate(arms):
            fr = rep['arms'][a][d]['frontier']
            xs = [p['MAE'] for p in fr]
            ys = [p[tail_key] for p in fr]
            lw = 2.6 if a.startswith('eq') else 1.6
            ax.plot(xs, ys, '-', color=COLORS[i % len(COLORS)], lw=lw, label=a)
            med = rep['arms'][a][d]['median_action']
            ax.plot(med['MAE'], med[tail_key], 'o', color=COLORS[i % len(COLORS)], ms=6)
            mean = rep['arms'][a][d]['mean_action']
            ax.plot(mean['MAE'], mean[tail_key], 's', color=COLORS[i % len(COLORS)], ms=5, mfc='none')
        ax.set_title(f'{d}: bulk vs tail frontier (o median, □ mean)')
        ax.set_xlabel('overall MAE (all records)')
        ax.set_ylabel(tail_key.replace('_', ' '))
        ax.grid(alpha=.3)
        ref = rep['arms'][arms[0]][d]['median_action']['MAE']
        ax.set_xlim(ref - 0.03, ref + 0.06)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / f'{name}_{tail_key.replace(">=", "ge").replace("_", "")}.png', dpi=130)
    plt.close(fig)


def bias_plot(rep, out):
    arms = list(rep['arms'])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, d in zip(axes, ('1s', '3s', '5s')):
        for i, a in enumerate(arms):
            rows = [r for r in rep['arms'][a][d]['by_magnitude_median'] if r['n'] > 0]
            ax.plot([r['lo'] + .25 for r in rows], [r['bias_median'] for r in rows], '-o', ms=3,
                    color=COLORS[i % len(COLORS)], lw=2.4 if a.startswith('eq') else 1.4, label=a)
        ax.axhline(0, color='k', lw=.8)
        ax.set_title(f'{d}: mean signed error of the median action')
        ax.set_xlabel('true magnitude (0.5 bins)')
        ax.grid(alpha=.3)
    axes[0].set_ylabel('prediction − truth')
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / 'bias_by_magnitude.png', dpi=130)
    plt.close(fig)


def response_plot(diag, out):
    arms = list(diag)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, d in zip(axes, ('1s', '3s', '5s')):
        for i, a in enumerate(arms):
            for f, ls in zip(diag[a]['amplitude_response'], ('-', '--', ':')):
                r = diag[a]['amplitude_response'][f]['M>=4'][d]
                xs = [float(k) for k in r if k[0] in '+-']
                ax.plot(xs, [r[k] for k in r if k[0] in '+-'], ls, marker='o', ms=3,
                        color=COLORS[i % len(COLORS)], label=f'{a} {f}')
        ax.plot([-1, 1], [-1, 1], 'k:', lw=.8, label='slope 1 (M_L definition)')
        ax.set_title(f'{d}: response of the median to amplitude ×10^δ (held-out M≥4)')
        ax.set_xlabel('δ (log10 amplitude change)')
        ax.grid(alpha=.3)
    axes[0].set_ylabel('change in predicted median')
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / 'amplitude_response.png', dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eval', required=True)
    ap.add_argument('--diag', default=None)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = json.loads(Path(args.eval).read_text())
    for key in ('M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE', 'CVaR95'):
        frontier_plot(rep, out, key)
    bias_plot(rep, out)
    if args.diag:
        response_plot(json.loads(Path(args.diag).read_text()), out)
    print('figures in', out)


if __name__ == '__main__':
    main()
