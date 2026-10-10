"""Independent NumPy replay of the two frozen distribution-grid reports.

No imports from either trainer, metric implementation or validator. Supports and
gates deliberately differ. P95/worst are supplementary, never new gate criteria.
"""
import math
import numpy as np

TIMES = (1, 3, 5)
SUBSETS = ("eval_seen", "eval_held")
SEEDS = (20261009, 20261010)
PANELS = {(t, s) for t in TIMES for s in SUBSETS}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def support(kind):
    need(kind in ("response", "exposure"), "Unknown grid")
    return (np.arange(66, dtype=np.float64) + (0 if kind == "response" else .5)) * .1


def probability(value, n):
    p = np.asarray(value, dtype=np.float64)
    need(p.shape == (n, 66) and np.isfinite(p).all() and (p >= 0).all(), "Invalid PMF shape/values")
    need(np.all(np.abs(p.sum(axis=1) - 1) <= 1e-8), "Unnormalized PMF; no repair allowed")
    return p


def quantile(values, weights, fraction):
    order = np.argsort(values, kind="stable")
    crossing = np.searchsorted(np.cumsum(weights[order]), fraction * weights.sum(), side="left")
    return float(values[order[min(int(crossing), len(order) - 1)]])


def event_average(values, events):
    ids, inverse, counts = np.unique(events, return_inverse=True, return_counts=True)
    return ids, np.bincount(inverse, weights=values) / counts


def point(prediction, y, w, event):
    pred, y, w, event = (np.asarray(x) for x in (prediction, y, w, event))
    need(len(y) > 0 and all(x.shape == y.shape for x in (pred, w, event)), "Unaligned point population")
    need(np.isfinite(pred).all() and np.isfinite(y).all() and np.isfinite(w).all() and (w > 0).all(), "Nonfinite point population")
    signed = pred - y
    error = np.abs(signed)
    ids, means = event_average(error, event)
    _, biases = event_average(signed, event)
    # Integrate the worst five percent of restoration mass, including a partial
    # boundary observation. A thresholded average is not weighted CVaR.
    order = np.argsort(-error, kind="stable")
    boundary = .05 * w.sum()
    cumulative = np.cumsum(w[order])
    used = np.maximum(0., np.minimum(cumulative, boundary) - np.minimum(cumulative - w[order], boundary))
    out = {"records": len(y), "events": len(ids), "weighted_mae": float(np.sum(w * error) / w.sum()),
           "weighted_rmse": float(np.sqrt(np.sum(w * signed ** 2) / w.sum())),
           "medae": quantile(error, w, .5), "weighted_bias": float(np.sum(w * signed) / w.sum()),
           "cvar95": float(np.sum(error[order] * used) / boundary),
           "event_macro_mae": float(means.mean()), "event_macro_bias": float(biases.mean()),
           "individual_events": {str(k): {"mae": float(a), "bias": float(b)} for k, a, b in zip(ids, means, biases)},
           "tail": {}, "supplementary": {"weighted_p95_abs_error": quantile(error, w, .95),
                                           "maximum_abs_error": float(error.max())}}
    for cutoff in (4, 5):
        keep = y >= cutoff
        tail_ids, tail_means = event_average(error[keep], event[keep])
        _, tail_bias = event_average(signed[keep], event[keep])
        row = {"records": int(keep.sum()), "events": len(tail_ids)}
        if keep.any():
            row.update(weighted_mae=float(np.sum(w[keep] * error[keep]) / w[keep].sum()),
                       weighted_bias=float(np.sum(w[keep] * signed[keep]) / w[keep].sum()),
                       event_macro_mae=float(tail_means.mean()), event_macro_bias=float(tail_bias.mean()))
        out["tail"][str(cutoff)] = row
    return out


def scores(p, y, w, event, kind):
    p = probability(p, len(y))
    y, w, event = np.asarray(y), np.asarray(w), np.asarray(event)
    centers = support(kind)
    cdf = np.cumsum(p, axis=1)
    mean = np.sum(p * centers, axis=1)
    median = centers[np.minimum(np.sum(cdf < .5, axis=1), 65)]
    out = {"mean": point(mean, y, w, event), "median": point(median, y, w, event)}
    # Independent CDF integral for exact continuous-target CRPS. On each support
    # interval the model CDF is constant; split it at the actual observed y.
    left, right = centers[:-1], centers[1:]
    below = np.clip(y[:, None] - left, 0, right - left)
    above = (right - left) - below
    crps = np.sum(cdf[:, :-1] ** 2 * below + (1 - cdf[:, :-1]) ** 2 * above, axis=1)
    crps += np.maximum(centers[0] - y, 0) + np.maximum(y - centers[-1], 0)
    average = lambda v: float(np.sum(w * v) / w.sum())
    raw = np.floor(y / .1 + 1e-5).astype(np.int64)
    valid_category = (y >= 0) & (raw >= 0) & (raw < 66)
    category = raw.clip(0, 65)
    tp = p[np.arange(len(y)), category]
    lo = np.minimum(np.sum(cdf < .05, axis=1), 65)
    hi = np.minimum(np.sum(cdf < .95, axis=1), 65)
    coverage = average((y >= centers[lo]) & (y <= centers[hi]))
    if kind == "response":
        dist = {"continuous_label_crps": average(crps),
                "clipped_category_nll": average(-np.log(tp)) if (tp > 0).all() else None,
                "nll_infinite": bool((tp == 0).any()),
                "outside_center_support_records": int(((y < centers[0]) | (y > centers[-1])).sum()),
                "center_interval90_coverage": coverage, "tail_calibration": {}}
    else:
        dist = {"continuous_crps": average(crps), "unsupported_category_records": int((~valid_category).sum()),
                "categorical_nll": None, "categorical_nll_infinite": False, "quantized_crps": None,
                "categorical_interval90_coverage": None, "continuous_center_interval90_coverage": coverage,
                "tail_probability": {}}
        if valid_category.all():
            dist["categorical_nll_infinite"] = bool((tp == 0).any())
            dist["categorical_nll"] = average(-np.log(tp)) if (tp > 0).all() else None
            dist["quantized_crps"] = average(.1 * np.sum((cdf[:, :-1] - (category[:, None] <= np.arange(65))) ** 2, axis=1))
            dist["categorical_interval90_coverage"] = average((category >= lo) & (category <= hi))
    for cutoff in (4, 5):
        tail = p[:, centers >= cutoff].sum(1)
        observed = y >= cutoff
        bins = np.minimum((tail * 10).astype(int), 9)
        rows = []
        for b in range(10):
            keep = bins == b
            row = {"bin": b, "records": int(keep.sum())}
            if kind == "exposure":
                row.update(weight=float(w[keep].sum()), events=len(np.unique(event[keep])))
            if keep.any():
                row.update(predicted=float(np.sum(w[keep] * tail[keep]) / w[keep].sum()),
                           observed=float(np.sum(w[keep] * observed[keep]) / w[keep].sum()))
            rows.append(row)
        if kind == "response":
            dist["tail_calibration"][str(cutoff)] = {"weighted_brier": average((tail - observed) ** 2), "bins": rows}
        else:
            dist["tail_probability"][str(cutoff)] = {"brier": average((tail - observed) ** 2), "reliability": rows}
    out["distribution"] = dist
    return out


def compare_values(actual, expected, path="value", atol=2e-10):
    """Compare a reported subtree to the independent replay, without dropping keys."""
    if isinstance(actual, dict):
        need(isinstance(expected, dict) and set(actual) == set(expected), path + " dictionary fields")
        for key, value in actual.items():
            need(key in expected, path + " unexpected field " + str(key))
            compare_values(value, expected[key], path + "." + str(key), atol)
    elif isinstance(actual, list):
        need(isinstance(expected, (list, tuple)) and len(actual) == len(expected), path + " list shape")
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare_values(a, e, path + "[" + str(i) + "]", atol)
    elif actual is None or isinstance(actual, (str, bool)):
        need(actual == expected, path + " differs")
    elif isinstance(actual, (int, float)) and not isinstance(actual, bool):
        need(isinstance(expected, (int, float, np.number)) and math.isfinite(actual) and math.isfinite(expected)
             and abs(actual - expected) <= atol, path + " numeric mismatch")
    else:
        raise ValueError(path + " unsupported value")


def reported_scores(full, kind):
    """Remove only the explicitly absent frozen fields before exact-schema check."""
    out = {"distribution": full["distribution"]}
    for action in ("mean", "median"):
        point = {k: v for k, v in full[action].items() if k != "supplementary"}
        if kind == "response":
            for key in ("weighted_rmse", "event_macro_bias"):
                point.pop(key)
            point["tail"] = {k: {a: b for a, b in v.items() if a != "event_macro_bias"} for k, v in point["tail"].items()}
        out[action] = point
    return out


def deltas(candidate, reference):
    result = {k: candidate[k] - reference[k] for k in ("weighted_mae", "medae")}
    for key, metric in (("m4_weighted_mae", "weighted_mae"), ("m4_event_macro_mae", "event_macro_mae")):
        result[key] = candidate["tail"]["4"].get(metric, 0) - reference["tail"]["4"].get(metric, 0) if candidate["tail"]["4"]["records"] else None
    return result


def bootstrap(candidate, reference, y, w, event, kind):
    """Frozen paired-event RNG law; no score/validator imports or fitted values."""
    centers = support(kind)
    a = np.abs(np.sum(candidate * centers, axis=1) - y)
    b = np.abs(np.sum(reference * centers, axis=1) - y)
    ids, inverse = np.unique(event, return_inverse=True)
    rng = np.random.default_rng(20261011)
    weighted_total = np.bincount(inverse, weights=w * (a - b))
    event_mass = np.bincount(inverse, weights=w)
    bulk, med = [], []
    if kind == "response":
        ao, bo = np.argsort(a, kind="stable"), np.argsort(b, kind="stable")
    for _ in range(1000):
        chosen = rng.integers(0, len(ids), size=len(ids))
        bulk.append(float(weighted_total[chosen].sum() / event_mass[chosen].sum()))
        if kind == "response":
            rw = w * np.bincount(chosen, minlength=len(ids))[inverse]
            def median(v, order):
                i = min(int(np.searchsorted(np.cumsum(rw[order]), .5 * rw.sum())), len(v) - 1)
                return v[order[i]]
            med.append(float(median(a, ao) - median(b, bo)))
    result = {"replicates": 1000, "seed": 20261011}
    if kind == "response":
        result.update(weighted_mae=np.quantile(bulk, [.025, .975]).tolist(), medae=np.quantile(med, [.025, .975]).tolist())
    else:
        result.update(weighted_mae_delta=float(weighted_total.sum() / event_mass.sum()),
                      weighted_mae_ci95=np.quantile(bulk, [.025, .975]).tolist())
    keep = y >= 4
    tail_ids, ti = np.unique(event[keep], return_inverse=True)
    if kind == "exposure":
        result["tail_events"] = len(tail_ids)
    if len(tail_ids):
        delta = (a - b)[keep]
        totals = np.bincount(ti, weights=w[keep] * delta)
        masses = np.bincount(ti, weights=w[keep])
        macro = np.bincount(ti, weights=delta) / np.bincount(ti)
        record_draws, macro_draws = [], []
        for _ in range(1000):
            chosen = rng.integers(0, len(tail_ids), size=len(tail_ids))
            macro_draws.append(float(macro[chosen].mean()))
            if kind == "response":
                record_draws.append(float(totals[chosen].sum() / masses[chosen].sum()))
        if kind == "response":
            result.update(m4_weighted_mae=np.quantile(record_draws, [.025, .975]).tolist(),
                          m4_event_macro_mae=np.quantile(macro_draws, [.025, .975]).tolist())
        else:
            result.update(m4_event_macro_mae_delta=float(macro.mean()),
                          m4_event_macro_mae_ci95=np.quantile(macro_draws, [.025, .975]).tolist())
    return result


def gate(rows, kind):
    """Recompute the exact predeclared gate, not a common cross-grid substitute."""
    if kind == "response":
        need(len(rows) == 6 and {(r["seconds"], r["subset"]) for r in rows} == PANELS, "Incomplete response comparisons")
        checks = []
        def effect(d):
            return all(d.get(k) is not None and math.isfinite(d[k]) and d[k] <= .002 for k in ("weighted_mae", "medae")) and all(d.get(k) is not None and math.isfinite(d[k]) and d[k] < 0 for k in ("m4_weighted_mae", "m4_event_macro_mae"))
        for row in rows:
            boot = row["bootstrap"]
            need(boot["replicates"] == 1000 and boot["seed"] == 20261011, "Wrong bootstrap law")
            bounds = {k: v[1] for k, v in boot.items() if isinstance(v, list)}
            required = {"weighted_mae", "medae", "m4_weighted_mae", "m4_event_macro_mae"}
            checks.append({"seconds": row["seconds"], "subset": row["subset"],
                "support": bool(row["m4_events"] >= 20 and row["valid_fraction"] >= .9),
                "both_seed_effects": set(row["seed_deltas"]) == {str(s) for s in SEEDS} and all(effect(d) for d in row["seed_deltas"].values()),
                "ensemble_uncertainty": set(bounds) == required and effect(bounds)})
        status = "inconclusive_support" if not all(c["support"] for c in checks) else "failed" if not all(c["both_seed_effects"] for c in checks) else "inconclusive_precision" if not all(c["ensemble_uncertainty"] for c in checks) else "pass"
        return {"status": status, "pass": status == "pass", "checks": checks,
                "scope": "Exploratory all-panel C-minus-B gate, not familywise confirmation"}
    need(kind == "exposure", "Unknown gate")
    expected = {(r, t, s) for r in ("huber_ce", "natural_ce") for t, s in PANELS}
    need(len(rows) == 12 and {(r["reference_control"], r["seconds"], r["subset"]) for r in rows} == expected, "Incomplete exposure comparisons")
    checks, enough = [], True
    for row in rows:
        c, r, boot = row["candidate"]["mean"], row["reference"]["mean"], row["bootstrap"]
        enough &= c["tail"]["4"]["events"] >= 20
        tail = c["tail"]["4"].get("event_macro_mae", np.inf) - r["tail"]["4"].get("event_macro_mae", 0.)
        passed = (c["weighted_mae"] - r["weighted_mae"] <= .002 and c["medae"] - r["medae"] <= .002 and tail <= -.02
                  and len(row["seed_m4_event_macro_deltas"]) == 2 and all(v is not None and math.isfinite(v) and v <= 0 for v in row["seed_m4_event_macro_deltas"])
                  and boot["replicates"] == 1000 and boot["seed"] == 20261011 and boot["weighted_mae_ci95"][1] <= .005
                  and boot.get("m4_event_macro_mae_ci95", [0, np.inf])[1] < 0 and row["valid_fraction"] >= .9)
        checks.append({"reference_control": row["reference_control"], "seconds": row["seconds"], "subset": row["subset"], "pass": bool(passed)})
    status = "inconclusive_tail_sample" if not enough else "pass" if all(c["pass"] for c in checks) else "failed"
    return {"pass": status == "pass", "status": status, "checks": checks,
            "scope": "Exploratory investment gate; no novelty or published superiority claim"}
