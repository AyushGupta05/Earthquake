"""Build tailrisk/tail_risk_study.ipynb: an explanatory notebook over the saved results.

The notebook reads the evaluation JSON and figures that evaluate.py /
make_figures.py / diagnostics.py wrote; it does not retrain anything.

  python tailrisk/build_notebook.py --eval <eval.json> [--diag <diag.json>] [--gbm <summary.json>]
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def md(text):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': text.strip('\n').splitlines(True)}


def code(text):
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [],
            'source': text.strip('\n').splitlines(True)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eval', required=True)
    ap.add_argument('--diag', default=None)
    ap.add_argument('--gbm', default=None)
    ap.add_argument('--seedcons', default=None, help='seed_consistency.py JSON (eqgr vs mix)')
    ap.add_argument('--hs-held', default=None, help='evaluate.py JSON on held-station records')
    ap.add_argument('--hs-seen', default=None, help='evaluate.py JSON on seen-station records')
    ap.add_argument('--magnet', default=None, help='evaluate.py JSON with the MagNet-style control')
    ap.add_argument('--findings', default=str(HERE / 'FINDINGS.md'))
    args = ap.parse_args()
    cells = [
        md("""
# Tail-risk study: scale-equivariant early magnitude distributions

This notebook explains every approach compared in `tailrisk/` and shows the saved
out-of-fold results. Nothing here retrains a model. The protocol and arm definitions are in
`tailrisk/README.md`. The narrative conclusions (positive and negative) are in
`tailrisk/FINDINGS.md`, reproduced at the end.

**Question.** From the first 1, 3 or 5 s after the P arrival at one station, can we reduce
the error on rare large earthquakes (M≥4, M≥5) *without* increasing the error on the bulk
of ordinary records?

**Key protocol choices**
1. *Leave-sequence-out CV.* All 1,159,249 INSTANCE records are split by Gardner–Knopoff
   aftershock sequences into 5 folds. The tail then has 346 M≥4 and 31 M≥5 events, instead of
   the 13 / 1 of the 2018 VAL split.
2. *Same trunk for every arm.* Only the predictive head / loss changes.
3. *Frontier evaluation.* For a posterior p, the rule "multiply the tail mass by r and take
   the median" is the Bayes action for the loss r·|e| on M≥4 and |e| otherwise. Sweeping r
   traces the best bulk/tail trade-off that p allows. We compare arms at *matched bulk MAE*.
"""),
        code("""
import json, pandas as pd
from IPython.display import Image, display
EVAL = %r
rep = json.load(open(EVAL))
print('records:', rep['n_records'], ' M>=4 events:', rep['n_M4_events'])
""" % args.eval),
        md("""
## 1. Point metrics of the fixed actions

`mean` is the posterior-mean action; `med` is the posterior median (r = 1). M≥4 MAE is
record-weighted; M≥4 eventMAE gives every M≥4 earthquake equal weight. CVaR95 is the mean of
the worst 5% of absolute errors over *all* records (the "largest errors" sense of long tail).
"""),
        code("""
rows = []
for arm, by_d in rep['arms'].items():
    for d, r in by_d.items():
        for act in ('mean_action', 'median_action'):
            m = r[act]
            rows.append({'arm': arm, 'deadline': d, 'action': act.split('_')[0], **{k: round(m[k], 4) for k in
                         ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE', 'M>=4_bias', 'FP4_rate')}})
pd.set_option('display.width', 200)
pd.DataFrame(rows).set_index(['deadline', 'action', 'arm']).sort_index()
"""),
        md("""
## 2. Bulk-constrained comparisons against the reference arm

For each bootstrap replicate (whole sequences resampled), each arm picks the tail weight r
that minimizes its tail error subject to bulk MAE ≤ the reference arm's median-action bulk MAE
(`bulkcap0_*`), or ≤ that value × 1.002 (`bulkcap0.002_*`). The table shows arm minus
reference; negative means the arm achieves a lower tail error without spending more bulk
error. Brackets are 95% intervals. `tailcap_MAE` is the reverse comparison: the least bulk
MAE subject to M≥4 MAE ≤ the reference's. `median`/`mean` rows compare the fixed actions.
"""),
        code("""
rows = []
for arm, by_d in rep.get('vs_ref', {}).items():
    for d, c in by_d.items():
        for key in ('bulkcap0_M>=4_MAE', 'bulkcap0_M>=4_eventMAE', 'bulkcap0_M>=5_MAE', 'bulkcap0.002_M>=4_MAE', 'tailcap_MAE'):
            v = c.get(key)
            if v:
                rows.append({'arm': arm, 'deadline': d, 'comparison': key, 'delta': round(v['mean'], 4),
                             'lo95': round(v['lo'], 4), 'hi95': round(v['hi'], 4), 'P(arm better)': round(v['p_arm_better'], 3)})
        for act in ('median', 'mean'):
            for key, v in c[act].items():
                if v:
                    rows.append({'arm': arm, 'deadline': d, 'comparison': f'{act} action {key}', 'delta': round(v['mean'], 4),
                                 'lo95': round(v['lo'], 4), 'hi95': round(v['hi'], 4), 'P(arm better)': round(v['p_arm_better'], 3)})
pd.DataFrame(rows).set_index(['comparison', 'deadline', 'arm']).sort_index()
"""),
        md("## 3. Frontiers\n\nEach curve is one arm's posterior evaluated over r. Lower-left is better. ● marks the median action, □ the mean action."),
        code("""
for f in ('frontier_Mge4MAE.png', 'frontier_Mge4eventMAE.png', 'frontier_Mge5MAE.png', 'frontier_CVaR95.png', 'bias_by_magnitude.png'):
    display(Image(filename='figures/' + f))
"""),
    ]
    if args.diag:
        cells += [md("""
## 4. Mechanism: does the prediction respond to amplitude?

We multiply the held-out ground motion by 10^δ and record the change in the predicted
median. For an amplitude-defined magnitude the change should be close to δ. A model that
saturates in the sparse upper tail moves much less. The equivariant head moves exactly
κ(s)·δ by construction; the free heads have to learn this response from data.
"""), code("""
display(Image(filename='figures/amplitude_response.png'))
diag = json.load(open(%r))
for arm, d in diag.items():
    for f, g in d['amplitude_response'].items():
        print(arm, f, {k: round(v['slope_up'], 3) for k, v in g['M>=4'].items()})
""" % args.diag)]
    if args.gbm:
        cells += [md("## 5. Classical feature + gradient-boosting baseline (E3WS-style)"), code("""
gbm = json.load(open(%r))
pd.DataFrame({d: {k: round(v[k], 4) for k in ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE')} for d, v in gbm.items()})
""" % args.gbm)]
    if args.seedcons:
        cells += [md("""
## 6. Seed × fold consistency

Three independently trained seeds of the new method and of the strongest baseline, compared
pairwise in every held-out fold and deadline (45 cells). A sign test asks whether the
improvement is systematic rather than carried by one fold or one seed.
"""), code("""
sc = json.load(open(%r))
pd.DataFrame({k: {'better / n': f"{v['n_better']}/{v['n']}", 'median Δ': round(v['median_delta'], 4), 'sign-test p': f"{v['p_sign']:.1e}",
                  **{d: f"{w['n_better']}/{w['n']}" for d, w in v['by_deadline'].items()}} for k, v in sc['summary'].items()}).T
""" % args.seedcons)]
    if args.hs_held and args.hs_seen:
        cells += [md("""
## 7. Held-station test

Arms suffixed `_hs` were trained with 20% of stations withheld in every fold. Records at those
stations in the held-out fold are *both* held-event and held-station, so station fingerprinting
cannot explain a gain there. The same arms are also scored on seen-station records.
"""), code("""
rows = []
for label, path in (('held stations', %r), ('seen stations', %r)):
    r = json.load(open(path))
    for arm, by_d in r['arms'].items():
        for d, v in by_d.items():
            m = v['median_action']
            rows.append({'subset': label, 'arm': arm, 'deadline': d, 'n': r['n_records'], **{k: round(m[k], 4) for k in ('MAE', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE')}})
    for arm, by_d in r.get('vs_ref', {}).items():
        for d, c in by_d.items():
            for key in ('MAE', 'M>=4_MAE', 'M>=5_MAE'):
                v = c['median'][key]
                rows.append({'subset': label, 'arm': f'{arm} − ref', 'deadline': d, 'n': r['n_records'], key: f"{v['mean']:+.4f} [{v['lo']:+.4f},{v['hi']:+.4f}]"})
pd.DataFrame(rows).set_index(['subset', 'deadline', 'arm']).sort_index()
""" % (args.hs_held, args.hs_seen))]
    if args.magnet:
        cells += [md("""
## 8. Published-architecture control

A MagNet-style CNN + BiLSTM trunk on amplitude-retaining waveforms (Mousavi & Beroza 2020
layout), given the same station metadata and trained with a Gaussian NLL on the same folds.
"""), code("""
r = json.load(open(%r))
pd.DataFrame({f"{arm} {d}": {k: round(v[d]['median_action'][k], 4) for k in ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=5_MAE')}
              for arm, v in r['arms'].items() for d in ('1s', '3s', '5s')}).T
""" % args.magnet)]
    findings = Path(args.findings)
    if findings.exists():
        cells.append(md('## Findings (from FINDINGS.md)\n\n' + findings.read_text()))
    for i, c in enumerate(cells):
        c['id'] = f'cell-{i:02d}'
    nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                       'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}
    out = HERE / 'tail_risk_study.ipynb'
    out.write_text(json.dumps(nb, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()
