"""Fixed natural-PMF evaluation; no action, seed, window or threshold selection."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from exposure_training import (CENTERS, HORIZONS, SEEDS, CONTROLS, PROTOCOL_SHA256,
                               digest_array, labels_and_support, predict_completed_grid,
                               require_completed_grid)


def checked_probability(probability, n):
    p = np.asarray(probability, dtype=np.float64)
    if p.shape != (n, 66) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError("Require finite nonnegative N x 66 probabilities")
    if not np.allclose(p.sum(1), 1, rtol=0, atol=1e-8):
        raise ValueError("Probabilities are not normalized; do not silently repair")
    return p


def pmf_mean(probability):
    # A direct bounded66-term sum avoids platform BLAS floating-status warnings
    # seen on macOS for otherwise finite probability-by-center products.
    return (np.asarray(probability, dtype=np.float64) * CENTERS[None]).sum(1)


def weighted_quantile(value, weight, q):
    order = np.argsort(value, kind="stable")
    index = np.searchsorted(np.cumsum(weight[order]), q * weight.sum(), side="left")
    return float(value[order[min(index, len(order) - 1)]])


def weighted_cvar(value, weight):
    order = np.argsort(-value, kind="stable")
    w = weight[order]
    amount = .05 * w.sum()
    previous = np.r_[0., np.cumsum(w)[:-1]]
    included = np.minimum(w, np.maximum(amount - previous, 0))
    return float(np.dot(value[order], included) / amount)


def event_means(value, events):
    ids, inverse = np.unique(events, return_inverse=True)
    return ids, np.bincount(inverse, weights=value) / np.bincount(inverse)


def point_metrics(prediction, population):
    prediction = np.asarray(prediction, dtype=np.float64)
    if prediction.shape != population.targets.shape or not np.isfinite(prediction).all():
        raise ValueError("Finite aligned point predictions required")
    y, w, events = population.targets, population.weights, population.events
    error = prediction - y
    absolute = np.abs(error)
    ids, emae = event_means(absolute, events)
    _, ebias = event_means(error, events)
    result = {"records": len(y), "events": len(ids), "weighted_mae": float(np.average(absolute, weights=w)),
              "weighted_rmse": float(np.sqrt(np.average(error ** 2, weights=w))),
              "weighted_bias": float(np.average(error, weights=w)),
              "medae": weighted_quantile(absolute, w, .5), "cvar95": weighted_cvar(absolute, w),
              "event_macro_mae": float(emae.mean()), "event_macro_bias": float(ebias.mean()),
              "tail": {}, "individual_events": {str(e): {"mae": float(m), "bias": float(b)}
                                                       for e, m, b in zip(ids, emae, ebias)}}
    for threshold in (4, 5):
        ix = y >= threshold
        tail_ids, tail_mae = event_means(absolute[ix], events[ix])
        _, tail_bias = event_means(error[ix], events[ix])
        result["tail"][str(threshold)] = {"records": int(ix.sum()), "events": len(tail_ids)}
        if ix.any():
            result["tail"][str(threshold)].update(
                weighted_mae=float(np.average(absolute[ix], weights=w[ix])),
                weighted_bias=float(np.average(error[ix], weights=w[ix])),
                event_macro_mae=float(tail_mae.mean()), event_macro_bias=float(tail_bias.mean()))
    return result


def distribution_scores(probability, population):
    p = checked_probability(probability, len(population.targets))
    y, w = population.targets, population.weights
    labels, support = labels_and_support(y)
    cdf = p.cumsum(1)
    previous_mass = np.c_[np.zeros(len(p)), cdf[:, :-1]]
    previous_moment = np.c_[np.zeros(len(p)), (p * CENTERS).cumsum(1)[:, :-1]]
    # Exact CRPS of a discrete PMF against the actual continuous target.
    crps = (p * np.abs(CENTERS[None] - y[:, None])).sum(1)
    crps -= (p * (CENTERS[None] * previous_mass - previous_moment)).sum(1)
    if (crps < -1e-8).any():
        raise ValueError("Negative CRPS beyond numerical tolerance")
    out = {"continuous_crps": float(np.average(crps, weights=w)),
           "unsupported_category_records": int((~support).sum()),
           "categorical_nll": None, "categorical_nll_infinite": False,
           "quantized_crps": None, "categorical_interval90_coverage": None}
    if support.all():
        true_p = p[np.arange(len(p)), labels]
        out["categorical_nll_infinite"] = bool((true_p == 0).any())
        if (true_p > 0).all():
            out["categorical_nll"] = float(np.average(-np.log(true_p), weights=w))
        observed = labels[:, None] <= np.arange(65)[None]
        out["quantized_crps"] = float(np.average(.1 * ((cdf[:, :-1] - observed) ** 2).sum(1), weights=w))
    lower = (cdf < .05).sum(1).clip(max=65)
    upper = (cdf < .95).sum(1).clip(max=65)
    out["continuous_center_interval90_coverage"] = float(np.average(
        (y >= CENTERS[lower]) & (y <= CENTERS[upper]), weights=w))
    if support.all():
        out["categorical_interval90_coverage"] = float(np.average((labels >= lower) & (labels <= upper), weights=w))
    out["tail_probability"] = {}
    for threshold in (4, 5):
        probability = p[:, CENTERS >= threshold].sum(1)
        observed = (y >= threshold).astype(float)
        bins = np.minimum((probability * 10).astype(int), 9)
        reliability = []
        for b in range(10):
            ix = bins == b
            row = {"bin": b, "records": int(ix.sum()), "weight": float(w[ix].sum()),
                   "events": len(np.unique(population.events[ix]))}
            if ix.any():
                row.update(predicted=float(np.average(probability[ix], weights=w[ix])),
                           observed=float(np.average(observed[ix], weights=w[ix])))
            reliability.append(row)
        out["tail_probability"][str(threshold)] = {
            "brier": float(np.average((probability - observed) ** 2, weights=w)),
            "reliability": reliability}
    return out


def score_pmf(probability, population, strata=None):
    """Unweighted within-event averages match the shared polarization protocol."""
    p = checked_probability(probability, len(population.targets))
    result = {"mean": point_metrics(pmf_mean(p), population),
              "median": point_metrics(CENTERS[(p.cumsum(1) < .5).sum(1).clip(max=65)], population),
              "distribution": distribution_scores(p, population), "strata": {}}
    # SimpleNamespace avoids reinterpreting partition identities on a row subset.
    for name, values in (strata or {}).items():
        if name not in ("unit", "family"):
            raise ValueError("Only frozen unit/family reporting strata are supported")
        values = np.asarray(values, dtype=str)
        if values.shape != population.targets.shape:
            raise ValueError("Reporting strata do not align with population rows")
        result["strata"][name] = {}
        for group in np.unique(values):
            ix = values == group
            sub = SimpleNamespace(targets=population.targets[ix], weights=population.weights[ix], events=population.events[ix])
            result["strata"][name][str(group)] = score_pmf(p[ix], sub)
    return result


def paired_bootstrap(candidate, reference, population):
    """Same bulk-then-tail RNG law as polarization v2; exactly1000 paired draws."""
    a = pmf_mean(checked_probability(candidate, len(population.targets)))
    b = pmf_mean(checked_probability(reference, len(population.targets)))
    delta = np.abs(a - population.targets) - np.abs(b - population.targets)
    ids, inverse = np.unique(population.events, return_inverse=True)
    total = np.bincount(inverse, weights=population.weights * delta)
    mass = np.bincount(inverse, weights=population.weights)
    rng = np.random.default_rng(20261011)
    draws = []
    for start in range(0, 1000, 32):
        sample = rng.integers(0, len(ids), size=(min(32, 1000 - start), len(ids)))
        draws.extend((total[sample].sum(1) / mass[sample].sum(1)).tolist())
    out = {"replicates": 1000, "seed": 20261011,
           "weighted_mae_delta": float(total.sum() / mass.sum()),
           "weighted_mae_ci95": np.quantile(draws, [.025, .975]).tolist()}
    tail = population.targets >= 4
    tail_ids, tail_delta = event_means(delta[tail], population.events[tail])
    out["tail_events"] = len(tail_ids)
    if len(tail_ids):
        draws = []
        for start in range(0, 1000, 32):
            sample = rng.integers(0, len(tail_ids), size=(min(32, 1000 - start), len(tail_ids)))
            draws.extend(tail_delta[sample].mean(1).tolist())
        out["m4_event_macro_mae_delta"] = float(tail_delta.mean())
        out["m4_event_macro_mae_ci95"] = np.quantile(draws, [.025, .975]).tolist()
    return out


def comparison(candidate_seeds, reference_seeds, population, *, valid_fraction):
    if set(candidate_seeds) != set(SEEDS) or set(reference_seeds) != set(SEEDS):
        raise ValueError("Both prespecified seeds required")
    if not np.isfinite(valid_fraction) or not 0 <= valid_fraction <= 1:
        raise ValueError("Shared-extractor validity fraction required")
    c = np.mean([checked_probability(candidate_seeds[s], len(population.targets)) for s in SEEDS], axis=0)
    r = np.mean([checked_probability(reference_seeds[s], len(population.targets)) for s in SEEDS], axis=0)
    cm, rm = score_pmf(c, population), score_pmf(r, population)
    seed_deltas = []
    for seed in SEEDS:
        cs = point_metrics(pmf_mean(candidate_seeds[seed]), population)
        rs = point_metrics(pmf_mean(reference_seeds[seed]), population)
        seed_deltas.append(cs["tail"]["4"]["event_macro_mae"] - rs["tail"]["4"]["event_macro_mae"]
                           if cs["tail"]["4"]["events"] else None)
    return {"seconds": population.seconds, "subset": population.subset, "candidate": cm, "reference": rm,
            "seed_m4_event_macro_deltas": seed_deltas, "bootstrap": paired_bootstrap(c, r, population),
            "valid_fraction": float(valid_fraction),
            "individual_event_mae_deltas": {event: cm["mean"]["individual_events"][event]["mae"] -
                                           rm["mean"]["individual_events"][event]["mae"]
                                           for event in cm["mean"]["individual_events"]}}


def investment_gate(rows):
    """All six panels against each of A/B, with no selected best comparison."""
    expected = {(r, t, s) for r in ("huber_ce", "natural_ce") for t in HORIZONS for s in ("eval_seen", "eval_held")}
    keys = {(r["reference_control"], r["seconds"], r["subset"]) for r in rows}
    if keys != expected or len(rows) != len(expected):
        return {"pass": False, "status": "incomplete"}
    checks, enough = [], True
    for row in rows:
        c, r, boot = row["candidate"]["mean"], row["reference"]["mean"], row["bootstrap"]
        enough &= c["tail"]["4"]["events"] >= 20
        tail_delta = c["tail"]["4"].get("event_macro_mae", np.inf) - r["tail"]["4"].get("event_macro_mae", 0.)
        passed = (c["weighted_mae"] - r["weighted_mae"] <= .002 and c["medae"] - r["medae"] <= .002
                  and tail_delta <= -.02 and len(row["seed_m4_event_macro_deltas"]) == 2
                  and all(v is not None and np.isfinite(v) and v <= 0 for v in row["seed_m4_event_macro_deltas"])
                  and boot["replicates"] == 1000 and boot["seed"] == 20261011
                  and boot["weighted_mae_ci95"][1] <= .005
                  and boot.get("m4_event_macro_mae_ci95", [0, np.inf])[1] < 0
                  and row["valid_fraction"] >= .9)
        checks.append({"reference_control": row["reference_control"], "seconds": row["seconds"],
                       "subset": row["subset"], "pass": bool(passed)})
    status = "inconclusive_tail_sample" if not enough else "pass" if all(x["pass"] for x in checks) else "failed"
    return {"pass": status == "pass", "status": status, "checks": checks,
            "scope": "Exploratory investment gate; no novelty or published superiority claim"}


def summarize_predictions(predictions, populations, strata, valid_fractions):
    """Pure metric helper; production callers use evaluate_completed_grid below."""
    panels = {(t, subset) for t in HORIZONS for subset in ("eval_seen", "eval_held")}
    keys = {(*key, t, subset) for key in ((c, s) for c in CONTROLS for s in SEEDS) for t, subset in panels}
    if set(predictions) != keys or set(populations) != panels or set(strata) != panels or set(valid_fractions) != panels:
        raise ValueError("All36 predictions and all6 populations/strata/validity fractions required")
    result = {"protocol_sha256": PROTOCOL_SHA256,
              "metrics_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "primary_action": "PMF mean", "scores": [], "comparisons": [],
              "matched_event_panels": [], "identities": []}
    ensemble = {}
    for t, subset in sorted(panels):
        p = populations[(t, subset)]
        if p.seconds != t or p.subset != subset or set(strata[(t, subset)]) != {"unit", "family"}:
            raise ValueError("Aligned held-panel identities and both unit/family strata required")
        result["identities"].append({"seconds": t, "subset": subset, "population": p.identity(),
            "strata": {k: digest_array(np.asarray(v, dtype=str)) for k, v in strata[(t, subset)].items()}})
        for control in CONTROLS:
            probability = {seed: checked_probability(predictions[(control, seed, t, subset)], len(p.targets)) for seed in SEEDS}
            ensemble[(control, t, subset)] = np.mean(list(probability.values()), axis=0)
            for name, pmf in [*( (str(seed), probability[seed]) for seed in SEEDS),
                              ("equal_pmf_ensemble", ensemble[(control, t, subset)])]:
                result["scores"].append({"control": control, "seed_or_ensemble": name,
                    "seconds": t, "subset": subset, "pmf_sha256": digest_array(pmf),
                    "metrics": score_pmf(pmf, p, strata[(t, subset)])})
        for reference in ("huber_ce", "natural_ce"):
            row = comparison({s: predictions[("band_exposure_ce", s, t, subset)] for s in SEEDS},
                             {s: predictions[(reference, s, t, subset)] for s in SEEDS}, p,
                             valid_fraction=valid_fractions[(t, subset)])
            row["reference_control"] = reference
            result["comparisons"].append(row)
    for t in HORIZONS:
        common = set(populations[(t, "eval_seen")].events) & set(populations[(t, "eval_held")].events)
        for subset in ("eval_seen", "eval_held"):
            p = populations[(t, subset)]
            ix = np.array([e in common for e in p.events])
            sub = SimpleNamespace(targets=p.targets[ix], weights=p.weights[ix], events=p.events[ix])
            for control in CONTROLS:
                metrics = point_metrics(pmf_mean(ensemble[(control, t, subset)])[ix], sub) if ix.any() else None
                result["matched_event_panels"].append({"seconds": t, "subset": subset, "control": control,
                    "common_events": len(common), "mean_action_metrics": metrics})
    result["gate"] = investment_gate(result["comparisons"])
    return result


def evaluate_completed_grid(directories, model_factory, loader, populations, strata,
                            valid_fractions, *, identity, population_validator, device="cpu"):
    """Single fixed-report entry point; completion checks precede model evaluation."""
    records = require_completed_grid(directories)
    probabilities = predict_completed_grid(directories, model_factory, loader, populations,
                                           identity=identity, population_validator=population_validator,
                                           device=device)
    report = summarize_predictions(probabilities, populations, strata, valid_fractions)
    report["checkpoints"] = [records[(c, s)] for c in CONTROLS for s in SEEDS]
    return report, probabilities
