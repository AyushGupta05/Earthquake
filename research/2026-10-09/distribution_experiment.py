"""Exploratory event-held-out readouts of frozen, previously selected CNNs.

Five outer event folds; next fold calibrates the decision rule, remaining three
fit the forest. This protects readout fitting/selection, NOT historical backbone
selection: every record is from a repeatedly used validation set.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import softmax
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import StratifiedKFold


def event_weights(ids):
    _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    w = 1. / counts[inverse]
    return w / w.sum()


def crps(prob, centers, target):
    """Exact CRPS of a discrete distribution, including targets off support."""
    before_p = np.cumsum(prob, axis=1) - prob
    before_m = np.cumsum(prob * centers, axis=1) - prob * centers
    return (prob * np.abs(centers[None, :] - target[:, None])).sum(1) - (
        prob * (centers * before_p - before_m)).sum(1)


def median(prob, centers):
    index = (np.cumsum(prob, axis=1) < .5).sum(1)
    return centers[np.minimum(index, len(centers)-1)]


def tilted(prob, centers, ratio):
    q = prob * np.where(centers >= 4., ratio, 1.)
    return q / q.sum(1, keepdims=True)


def metrics(y, pred, ids, prob=None, centers=None):
    e = np.abs(pred-y)
    w = event_weights(ids)
    n_worst = max(1, int(np.ceil(.05 * len(y))))
    tail = y >= 4.
    negative = ~tail
    result = dict(mae=float(e.mean()), medae=float(np.median(e)),
                  rmse=float(np.sqrt(np.mean(e**2))),
                  event_macro_mae=float(w @ e),
                  cvar95=float(np.sort(e)[-n_worst:].mean()),
                  fp4=int(((pred >= 4.) & negative).sum()),
                  tp4=int(((pred >= 4.) & tail).sum()),
                  fpr4=float((pred[negative] >= 4.).mean()) if negative.any() else None,
                  records=len(y), events=len(np.unique(ids)))
    for threshold in [4., 4.5, 5., 6.]:
        mask = y >= threshold
        key = f'm{threshold:g}'
        result[key+'_events'] = len(np.unique(ids[mask]))
        result[key+'_mae'] = float(e[mask].mean()) if mask.any() else None
        result[key+'_event_macro_mae'] = float(event_weights(ids[mask]) @ e[mask]) if mask.any() else None
        result[key+'_bias'] = float((pred[mask]-y[mask]).mean()) if mask.any() else None
    if prob is not None:
        result['crps'] = float(crps(prob, centers, y).mean())
        result['tail_crps4'] = float(crps(prob, np.maximum(centers, 4.), np.maximum(y, 4.)).mean())
        p4 = prob[:, centers >= 4.].sum(1)
        result['brier4'] = float(np.mean((p4-tail)**2))
    return result


def safe_choice(y, ids, raw, candidates):
    """Fixed empirical tolerances; not a population risk guarantee."""
    base = metrics(y, raw, ids)
    selected, best = 'raw_fallback', base['m4_event_macro_mae']
    if best is None:
        return selected
    for name, prediction in candidates.items():
        m = metrics(y, prediction, ids)
        feasible = (m['mae'] <= base['mae'] + .01 and
                    m['medae'] <= base['medae'] + .01 and
                    m['rmse'] <= base['rmse'] + .01 and
                    m['event_macro_mae'] <= base['event_macro_mae'] + .01 and
                    m['cvar95'] <= base['cvar95'] + .02 and
                    m['fpr4'] <= base['fpr4'] + .002)
        if feasible and m['m4_event_macro_mae'] < best:
            selected, best = name, m['m4_event_macro_mae']
    return selected


def event_folds(y, ids):
    events, first, inverse = np.unique(ids, return_index=True, return_inverse=True)
    labels = y[first] >= 4.
    if min(np.bincount(labels.astype(int), minlength=2)) < 5:
        raise ValueError('Need at least five distinct tail and non-tail events')
    assignment = np.empty(len(events), dtype=int)
    for k, (_, test) in enumerate(StratifiedKFold(5, shuffle=True, random_state=20261009).split(events, labels)):
        assignment[test] = k
    return assignment[inverse]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trees', type=int, default=64)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = np.load(args.input, allow_pickle=False)
    logits, y, ids = data['logits'].astype(float), data['targets'], data['event_ids']
    c, prior = data['centers'], data['train_prior']
    p = softmax(logits, axis=1)
    raw = p @ c
    curve = np.column_stack([softmax(logits + (a-1.)*np.log(prior), axis=1) @ c
                             for a in [1., .25, .5, .75, 1.25]])
    curve[:, 1:] -= curve[:, :1]
    features = {'mean': raw[:, None], 'probe5': curve, 'full66': p}
    assignments = event_folds(y, ids)
    label = np.clip(np.floor(y/.1 + 1e-5).astype(int), 0, len(c)-1)
    predictions = {'raw_mean': raw, 'raw_median': median(p, c),
                   'raw_cost11_median': median(tilted(p, c, 11.), c)}
    distributions = {'raw_mean': p, 'raw_median': p}
    fold_log = []
    for family, x in features.items():
        pp = np.empty_like(p)
        decision = np.empty_like(y)
        for fold in range(5):
            test = assignments == fold
            cal = assignments == (fold+1) % 5
            train = ~(test | cal)
            assert not set(ids[train]) & set(ids[test])
            assert not set(ids[cal]) & set(ids[test])
            model = ExtraTreesClassifier(n_estimators=args.trees, max_depth=16,
                min_samples_leaf=50, max_features=1., n_jobs=2, random_state=20261009+fold)
            model.fit(x[train], label[train], sample_weight=event_weights(ids[train])*train.sum())
            probs = []
            for subset in [cal, test]:
                q = np.zeros((subset.sum(), len(c)))
                q[:, model.classes_] = model.predict_proba(x[subset])
                # A fixed training-only prior mixture prevents zero support.
                q = (1-1e-4)*q + 1e-4*prior
                probs.append(q)
            cal_q, test_q = probs
            pp[test] = test_q
            cal_actions, test_actions = {}, {}
            for ratio in [1., 2., 4., 8., 11.]:
                for blend in [.25, .5, 1.]:
                    name = f'ratio{ratio:g}_blend{blend:g}'
                    cal_actions[name] = raw[cal] + blend*(median(tilted(cal_q, c, ratio), c)-raw[cal])
                    test_actions[name] = raw[test] + blend*(median(tilted(test_q, c, ratio), c)-raw[test])
            choice = safe_choice(y[cal], ids[cal], raw[cal], cal_actions)
            decision[test] = raw[test] if choice == 'raw_fallback' else test_actions[choice]
            fold_log.append({'family': family, 'fold': fold, 'choice': choice,
                'train_events': len(np.unique(ids[train])), 'cal_events': len(np.unique(ids[cal])),
                'test_events': len(np.unique(ids[test])),
                'test_m4_events': len(np.unique(ids[test & (y>=4)]))})
            print(args.input.name, family, fold, choice, flush=True)
        for suffix, pred in [('mean', pp @ c), ('median', median(pp,c)),
                             ('cost11_median', median(tilted(pp,c,11.),c)), ('selected', decision)]:
            key = f'{family}_{suffix}'
            predictions[key] = pred
            # Cost-shifted decisions are not rebranded as calibrated probabilities.
            if suffix in ['mean', 'median']:
                distributions[key] = pp
    result = {name: metrics(y, pred, ids, distributions.get(name), c)
              for name, pred in predictions.items()}
    (args.output / 'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    (args.output / 'folds.json').write_text(json.dumps(fold_log, indent=2)+'\n')
    pd.DataFrame(result).T.to_csv(args.output / 'metrics.csv')
    np.savez_compressed(args.output / 'predictions.npz', targets=y, event_ids=ids,
                        fold=assignments, **predictions)
    print(pd.DataFrame(result).T[['mae','medae','m4_mae','m4_event_macro_mae','cvar95','fp4']].to_string())


if __name__ == '__main__':
    main()
