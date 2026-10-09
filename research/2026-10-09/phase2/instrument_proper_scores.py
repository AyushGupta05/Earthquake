"""Established ordinal-score controls; no contextual/OOF reference is claimed."""
import numpy as np
import torch
from torch.nn import functional as F

CONTROLS = ('huber_ce', 'crps_ce', 'tail_crps_ce', 'marginal_crps_ce', 'ranked_bce_ce')
BIN_WIDTH = .1
CE_WEIGHT = .075
PRIOR_EPSILON = .01
PRIOR_CAP = 25.


def magnitude_labels(y, num_bins=66):
    return np.clip(np.floor(np.asarray(y, dtype=np.float64) / BIN_WIDTH + 1e-5), 0, num_bins-1).astype(np.int64)


def train_marginal_weights(train_y, population_weights, num_bins=66):
    """Fit a single threshold vector from TRAIN labels and inclusion weights.

    No validation argument, current prediction, or per-record reference enters
    this estimator. It represents the TRAIN *record* population, not uniform
    event weights. A cap and fixed threshold-mean normalization prevent empty
    extreme bins from producing infinities. This is not an OOF reference model.
    """
    y = np.asarray(train_y, dtype=np.float64)
    w = np.asarray(population_weights, dtype=np.float64)
    if num_bins < 2 or y.ndim != 1 or not len(y) or w.shape != y.shape:
        raise ValueError('Require aligned nonempty TRAIN labels/weights and at least two bins')
    if not np.isfinite(y).all() or not np.isfinite(w).all() or (w <= 0).any():
        raise ValueError('TRAIN labels must be finite and population weights finite positive')
    histogram = np.bincount(magnitude_labels(y, num_bins), weights=w, minlength=num_bins)
    cdf = np.cumsum(histogram)[:-1] / histogram.sum()
    cdf = np.clip(cdf, 0., 1.)
    unnormalized = np.minimum(PRIOR_CAP, 1. / (PRIOR_EPSILON + cdf * (1 - cdf)))
    normalizer = float(unnormalized.mean())
    weights = (unnormalized / normalizer).astype(np.float32)
    return weights, {'source_split': 'train', 'records': len(y),
        'population_weight_sum': float(w.sum()), 'weighted_bin_mass': histogram.tolist(),
        'cdf': cdf.tolist(), 'epsilon': PRIOR_EPSILON, 'cap': PRIOR_CAP,
        'normalization': 'Arithmetic mean across the fixed interior magnitude thresholds',
        'normalizer': normalizer, 'weights': weights.tolist(),
        'clipped_threshold_fraction': float(np.mean(unnormalized == PRIOR_CAP))}


def fixed_tail_weights(num_bins=66, device=None, dtype=torch.float32):
    """Interior cut z=(k+1)*.1: weight 5 starting exactly at z=4, else 1."""
    if num_bins < 2:
        raise ValueError('Need at least two magnitude bins')
    cut_indices = torch.arange(1, num_bins, device=device)
    return 1 + 4 * (cut_indices >= 40).to(dtype)


def ranked_score(logits, labels, threshold_weights=None, logarithmic=False):
    """Unreduced discrete-grid CRPS or ranked binary log score, spacing .1.

    Stable log-cumulative sums avoid log(0), clipping bias, and 0*infinity in
    the ranked-BCE control even for extremely separated finite logits.
    """
    if logits.ndim != 2 or logits.shape[1] < 2 or labels.shape != (len(logits),):
        raise ValueError('Require B x K logits and one bin label per row, K>=2')
    if labels.dtype != torch.int64:
        raise TypeError('Bin labels must be int64')
    if torch.any(labels < 0) or torch.any(labels >= logits.shape[1]):
        raise ValueError('Bin label outside the probability grid')
    if threshold_weights is not None:
        if threshold_weights.shape != (logits.shape[1]-1,):
            raise ValueError('One fixed weight per interior threshold is required')
        if not torch.isfinite(threshold_weights).all() or (threshold_weights <= 0).any():
            raise ValueError('Threshold weights must be finite positive')
    observed = labels[:, None] <= torch.arange(logits.shape[1]-1, device=logits.device)
    if logarithmic:
        log_z = logits.logsumexp(-1, keepdim=True)
        log_cdf = logits.logcumsumexp(-1)[:, :-1] - log_z
        log_survival = logits.flip(-1).logcumsumexp(-1).flip(-1)[:, 1:] - log_z
        boundary = torch.where(observed, -log_cdf, -log_survival)
    else:
        cdf = logits.softmax(-1).cumsum(-1)[:, :-1].clamp(0., 1.)
        boundary = (cdf - observed.to(cdf.dtype)).square()
    if threshold_weights is not None:
        boundary = boundary * threshold_weights
    return BIN_WIDTH * boundary.sum(-1)


def objective_vector(logits, y, labels, centers, original_mean, control, marginal_weights):
    """Exact existing beta=5 Huber/CE, or an established proper grid score+CE.

    The Huber path intentionally preserves the original zero-weight anchor
    expression and its operation order for a matched numerical negative control.
    No reference weights enter that path. The other four objectives omit Huber.
    """
    if control not in CONTROLS:
        raise ValueError('Unknown score control')
    if control == 'huber_ce':
        pred = logits.softmax(1) @ centers
        magnitude = F.huber_loss(pred, y, reduction='none', delta=.5)
        emphasis = 1 + 5. * (y - 3.5).clamp_min(0)
        ce = F.cross_entropy(logits, labels, reduction='none')
        anchor = (pred - original_mean).square()
        return emphasis * magnitude + CE_WEIGHT * ce + 0. * anchor
    ce = F.cross_entropy(logits, labels, reduction='none')
    threshold_weights = None
    if control == 'tail_crps_ce':
        threshold_weights = fixed_tail_weights(logits.shape[1], logits.device, logits.dtype)
    elif control == 'marginal_crps_ce':
        threshold_weights = marginal_weights
        if threshold_weights is None:
            raise ValueError('Marginal score requires the frozen TRAIN threshold vector')
    score = ranked_score(logits, labels, threshold_weights,
                         logarithmic=control == 'ranked_bce_ce')
    return score + CE_WEIGHT * ce
