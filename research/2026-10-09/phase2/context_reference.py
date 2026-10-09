"""Frozen event-cross-fitted threshold metrics; known proper-score construction.

Teachers see 51 target-free prefix descriptors plus 34 static instrument/site
fields, never the all-TRAIN CNN logits/embedding. Students retain that existing
pipeline. Conditional propriety is a population statement for exogenous positive
weights, not a finite-sample calibration or point-error guarantee.
"""
import hashlib
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from instrument_residual import weighted_normalizer
from instrument_proper_scores import magnitude_labels, ranked_score
from train_instrument_scores import array_digest, model_digest

CONTROLS = ('crps_ce', 'context_ce', 'shuffled_ce', 'average_ce',
            'ranked_bce_ce', 'properized_ad_ce')
EPSILON, CAP, CE_WEIGHT, BIN_WIDTH = .01, 25., .075, .1
REFERENCE_DIM, NUM_BINS = 85, 66


def reference_inputs(data):
    """No labels, CNN tensors, native slots or validation inputs are read."""
    prefix, static = data['train_prefix'], data['train_instrument']
    if prefix.ndim != 2 or prefix.shape[1] != 51 or static.shape != (len(prefix), 34):
        raise ValueError('Reference requires exactly 51 prefix plus 34 static fields')
    x = np.concatenate([prefix, static], axis=1).astype(np.float32)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError('Reference input must be nonempty and finite')
    return x


def event_folds(event_ids, n_folds=5, seed=20261009):
    """Target-independent SHA256 partition, invariant to row order/count."""
    ids = np.asarray(event_ids)
    if ids.ndim != 1 or ids.dtype.kind not in 'US' or n_folds < 2 or not len(ids):
        raise ValueError('Require string event identities and at least two folds')
    if np.any(ids == ''):
        raise ValueError('Empty event identity')
    mapping = {s: int.from_bytes(hashlib.sha256(f'{seed}:{s}'.encode()).digest()[:8], 'big') % n_folds
               for s in np.unique(ids).tolist()}
    folds = np.array([mapping[s] for s in ids], dtype=np.int64)
    if set(folds.tolist()) != set(range(n_folds)):
        raise ValueError('Every reference fold must contain at least one event')
    return folds


def reference_weights(probability):
    p = np.asarray(probability, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] < 2 or not len(p) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError('Invalid reference probabilities')
    if not np.allclose(p.sum(1), 1., atol=1e-7, rtol=1e-7):
        raise ValueError('Reference probability rows must sum to one')
    cdf = np.clip(p.cumsum(1)[:, :-1], 0., 1.)
    unbounded = 1. / (EPSILON + cdf * (1. - cdf))
    capped = np.minimum(CAP, unbounded)
    weights = capped / capped.mean(1, keepdims=True)
    return weights.astype(np.float32), cdf, unbounded >= CAP


def weight_controls(weights, population_weights, folds, event_ids, seed=20261012):
    """Permutation is label-free and only among rows excluded by SAME teacher.

    Same-event donors/fixed points are permitted and reported, not secretly
    rejected using labels. Population-weighted threshold means can change under
    row permutation when inclusion weights differ; report this diagnostic.
    """
    w, pop, folds, ids = map(np.asarray, (weights, population_weights, folds, event_ids))
    n = len(w)
    if w.ndim != 2 or w.shape[1] < 1 or any(v.shape != (n,) for v in (pop, folds, ids)):
        raise ValueError('Misaligned weight-control inputs')
    if not np.isfinite(w).all() or (w <= 0).any() or not np.allclose(w.mean(1), 1., atol=2e-6):
        raise ValueError('Reference weights must be finite positive and row-mean one')
    if not np.isfinite(pop).all() or (pop <= 0).any():
        raise ValueError('Invalid population weights')
    rng = np.random.default_rng(seed)
    donor = np.arange(n)
    for k in np.unique(folds):
        rows = np.flatnonzero(folds == k)
        donor[rows] = rng.permutation(rows)
    if not np.array_equal(folds[donor], folds):
        raise AssertionError('Permutation crossed teacher exclusion folds')
    average = np.average(w.astype(np.float64), weights=pop, axis=0).astype(np.float32)
    shuffled_mean = np.average(w[donor].astype(np.float64), weights=pop, axis=0)
    report = {'seed': seed, 'fixed_point_fraction': float(np.mean(donor == np.arange(n))),
        'same_event_donor_fraction': float(np.mean(ids[donor] == ids)),
        'max_population_weighted_threshold_mean_change': float(np.max(np.abs(shuffled_mean-average))),
        'donor_sha256': array_digest(donor), 'average_sha256': array_digest(average)}
    return donor, average, report


class ReferenceDistribution(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(REFERENCE_DIM, 128), nn.SiLU(), nn.Dropout(.1),
                                 nn.Linear(128, 64), nn.SiLU(), nn.Linear(64, NUM_BINS))

    def forward(self, descriptors):
        return self.net(descriptors)


def fit_reference_fold(x, labels, population_weights, folds, held_fold, args, device):
    """Only retained fold labels/weights enter teacher fit and normalization."""
    x, labels, pop, folds = map(np.asarray, (x, labels, population_weights, folds))
    n = len(x)
    if x.shape != (n, REFERENCE_DIM) or any(v.shape != (n,) for v in (labels, pop, folds)):
        raise ValueError('Misaligned reference fold arrays')
    train, held = np.flatnonzero(folds != held_fold), np.flatnonzero(folds == held_fold)
    if not len(train) or not len(held) or not np.isfinite(x).all():
        raise ValueError('Empty or invalid reference fold')
    train_labels = labels[train]
    if train_labels.dtype != np.int64 or np.any(train_labels < 0) or np.any(train_labels >= NUM_BINS):
        raise ValueError('Invalid retained-fold bin labels')
    if min(args.reference_epochs, args.batch_size) < 1 or not np.isfinite(args.reference_learning_rate) or args.reference_learning_rate <= 0:
        raise ValueError('Invalid reference optimization bounds')
    mean, std = weighted_normalizer(x[train], pop[train])
    train_x = torch.as_tensor(np.clip((x[train] - mean) / std, -15, 15), device=device)
    held_x = torch.as_tensor(np.clip((x[held] - mean) / std, -15, 15), device=device)
    y = torch.as_tensor(train_labels, device=device)
    w = torch.as_tensor((pop[train] / pop[train].mean()).astype(np.float32), device=device)
    seed = int(args.reference_seed + held_fold)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = ReferenceDistribution().to(device)
    initial = model_digest(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.reference_learning_rate, weight_decay=1e-4)
    generator = torch.Generator(device='cpu').manual_seed(seed)
    history, orders = [], []
    for _ in range(args.reference_epochs):
        model.train()
        order = torch.randperm(len(train), generator=generator)
        orders.append(array_digest(order.numpy()))
        total = 0.
        for ix_cpu in order.split(args.batch_size):
            ix = ix_cpu.to(device)
            loss = (w[ix] * F.cross_entropy(model(train_x[ix]), y[ix], reduction='none')).mean()
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite reference CE')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
            total += loss.item() * len(ix)
        history.append(total / len(train))
    model.eval()
    with torch.inference_mode():
        logp = torch.cat([model(block).double().log_softmax(1).cpu()
                         for block in held_x.split(args.batch_size)]).numpy()
    report = {'held_fold': int(held_fold), 'seed': seed, 'train_records': len(train), 'held_records': len(held),
        'train_indices_sha256': array_digest(train), 'held_indices_sha256': array_digest(held),
        'normalizer_mean_sha256': array_digest(mean), 'normalizer_std_sha256': array_digest(std),
        'initial_model_sha256': initial, 'final_model_sha256': model_digest(model),
        'epoch_order_sha256': orders, 'history': history}
    state = {'model': model.cpu().state_dict(), 'feature_mean': torch.tensor(mean), 'feature_std': torch.tensor(std),
             'seed': seed, 'held_fold': int(held_fold), 'feature_dimension': REFERENCE_DIM}
    return held, logp, state, report


def fit_references(data, args, device, destination=None):
    x = reference_inputs(data)
    ids, y, pop = data['train_ids'], data['train_y'], data['weights']
    if any(np.asarray(v).shape != (len(x),) for v in (ids, y, pop)) or not np.isfinite(y).all():
        raise ValueError('Reference TRAIN rows misaligned')
    if not np.isfinite(pop).all() or (pop <= 0).any():
        raise ValueError('Invalid TRAIN population weights')
    folds = event_folds(ids, args.reference_folds, args.fold_seed)
    labels = magnitude_labels(y)
    logp = np.full((len(x), NUM_BINS), np.nan, dtype=np.float64)
    reports = []
    for k in range(args.reference_folds):
        held, prediction, state, report = fit_reference_fold(x, labels, pop, folds, k, args, device)
        logp[held] = prediction
        report.update(train_events=len(np.unique(ids[folds != k])), held_events=len(np.unique(ids[held])))
        reports.append(report)
        if destination is not None:
            torch.save(state, destination / f'reference_fold{k}.pth')
        print('REFERENCE_FOLD', k, 'train', report['train_records'], 'held', len(held), flush=True)
    if not np.isfinite(logp).all():
        raise ValueError('Incomplete or nonfinite OOF reference predictions')
    probability = np.exp(logp)
    weights, cdf, capped = reference_weights(probability)
    donor, average, shuffle_report = weight_controls(weights, pop, folds, ids, args.permutation_seed)
    nll = -logp[np.arange(len(x)), labels]
    def quantiles(a):
        return dict(zip(('min','q01','q25','median','q75','q99','max'),
                        np.quantile(a, [0,.01,.25,.5,.75,.99,1]).tolist()))
    report = {'feature_names': '51 existing prefix_features slots + 34 instrument schema fields; no CNN/native',
        'n_folds': args.reference_folds, 'fold_seed': args.fold_seed, 'reference_seed': args.reference_seed,
        'folds': reports, 'population_weighted_oof_nll': float(np.average(nll, weights=pop)),
        'oof_nll': float(nll.mean()), 'nll_quantiles': quantiles(nll),
        'probability_quantiles': quantiles(probability), 'cdf_quantiles': quantiles(cdf),
        'weight_quantiles': quantiles(weights), 'capped_fraction': float(capped.mean()),
        'row_mean_max_error': float(np.abs(weights.mean(1)-1).max()),
        'average_threshold_weights': average.tolist(), 'permutation': shuffle_report,
        'input_sha256': array_digest(x), 'fold_sha256': array_digest(folds),
        'probability_sha256': array_digest(probability), 'weight_sha256': array_digest(weights),
        'weighted_population': 'Inverse-inclusion recording population, not equal event weights'}
    return {'probability': probability, 'weights': weights, 'folds': folds,
            'donor': donor, 'average': average}, report


def score_vector(logits, labels, control, threshold_weights=None):
    """Known proper interior-threshold scores plus unchanged categorical CE."""
    if control not in CONTROLS:
        raise ValueError('Unknown contextual score control')
    if logits.ndim != 2 or logits.shape[1] < 2 or labels.shape != (len(logits),) or labels.dtype != torch.int64:
        raise ValueError('Require B x K logits and aligned int64 labels')
    if not torch.isfinite(logits).all() or (labels < 0).any() or (labels >= logits.shape[1]).any():
        raise ValueError('Invalid logits or magnitude bin')
    # Same graph construction order as the existing proper-score baseline.
    ce = F.cross_entropy(logits, labels, reduction='none')
    if control in ('crps_ce', 'ranked_bce_ce'):
        score = ranked_score(logits, labels, logarithmic=control == 'ranked_bce_ce')
    elif control == 'properized_ad_ce':
        # Barczy Prop1.3, Eq1.5: exp(+/- log(CDF/survival)/2).
        # Double log-cumulative sums avoid cancellation; no probability clipping
        # or exponent cap that would silently change the proper score. Abort on
        # unrepresentable float32-backbone gradients instead of reporting a win.
        z = logits.double()
        log_cdf_unnormalized = z.logcumsumexp(-1)[:, :-1]
        log_survival_unnormalized = z.flip(-1).logcumsumexp(-1).flip(-1)[:, 1:]
        half_log_odds = .5 * (log_cdf_unnormalized-log_survival_unnormalized)
        observed = labels[:, None] <= torch.arange(logits.shape[1]-1, device=logits.device)
        exponent = torch.where(observed, -half_log_odds, half_log_odds)
        if exponent.max() > 60:
            raise FloatingPointError('Properized AD exponent exceeds prespecified float32-backbone safety bound 60; no clipping applied')
        score = BIN_WIDTH * exponent.exp().sum(-1)
    else:
        w = threshold_weights
        if w is None or w.shape not in ((logits.shape[1]-1,), (len(logits), logits.shape[1]-1)):
            raise ValueError('Context/average score requires aligned frozen threshold weights')
        if w.requires_grad or not torch.isfinite(w).all() or (w <= 0).any():
            raise ValueError('Weights must be fixed finite positive tensors')
        if not torch.allclose(w.mean(-1), torch.ones_like(w.mean(-1)), atol=2e-6, rtol=0):
            raise ValueError('Weights must have fixed per-vector arithmetic mean one')
        observed = labels[:, None] <= torch.arange(logits.shape[1]-1, device=logits.device)
        cdf = logits.softmax(-1).cumsum(-1)[:, :-1].clamp(0., 1.)
        score = BIN_WIDTH * ((cdf-observed.to(cdf.dtype)).square()*w).sum(-1)
    return score + CE_WEIGHT * ce
