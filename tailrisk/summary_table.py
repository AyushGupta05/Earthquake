"""Markdown headline tables from an evaluate.py report (+ optional GBM summary).

  python tailrisk/summary_table.py --eval results/eval_X.json [--gbm results/gbm_e3ws_summary.json]
"""
import argparse
import json
from pathlib import Path

COLS = [('MAE', 'bulk MAE'), ('MedAE', 'MedAE'), ('CVaR95', 'CVaR95'), ('M>=4_MAE', 'M≥4 MAE'),
        ('M>=4_eventMAE', 'M≥4 event'), ('M>=5_MAE', 'M≥5 MAE'), ('M>=4_bias', 'M≥4 bias'), ('FP4_rate', 'false-M4')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eval', required=True)
    ap.add_argument('--gbm', default=None)
    ap.add_argument('--action', default='median_action', choices=['median_action', 'mean_action'])
    args = ap.parse_args()
    rep = json.loads(Path(args.eval).read_text())
    gbm = json.loads(Path(args.gbm).read_text()) if args.gbm else None
    for d in ('1s', '3s', '5s'):
        print(f'\n**{d}** ({args.action.replace("_", " ")})\n')
        print('| arm | ' + ' | '.join(c[1] for c in COLS) + ' | NLL | Brier M≥5 |')
        print('|---|' + '---|' * (len(COLS) + 2))
        for arm, r in rep['arms'].items():
            m = r[d][args.action]
            print(f'| {arm} | ' + ' | '.join(f'{m[k]:.4f}' if k not in ('FP4_rate',) else f'{m[k]:.4f}' for k, _ in COLS)
                  + f' | {r[d]["nll_bin"]:.4f} | {r[d].get("brier_M5", float("nan")):.6f} |')
        if gbm:
            m = gbm[d]
            print('| gbm_e3ws (point) | ' + ' | '.join(f'{m[k]:.4f}' for k, _ in COLS) + ' | – | – |')


if __name__ == '__main__':
    main()
