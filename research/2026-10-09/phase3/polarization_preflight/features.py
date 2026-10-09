"""Prefix-only NumPy descriptors; no targets, catalog geometry, fitting or GPU."""
import numpy as np

COMPONENTS = 'ENZ'
PAIRS = ((0, 1), (0, 2), (1, 2))
BANDS = ((0, 2), (2, 5), (5, 10), (10, 20), (20, 51))
BASE_NAMES = (
    [f'counts_log10_{s}_{c}' for s in ('rms', 'peak', 'mean_abs') for c in COMPONENTS]
    + [f'quarter_rms_ratio_{c}_{q}' for c in COMPONENTS for q in range(4)]
    + [f'prefix_band_{c}_{lo}_{hi}' for c in COMPONENTS for lo, hi in BANDS]
    + [f'{s}_{c}' for s in ('centroid', 'entropy', 'crossings', 'roughness', 'crest') for c in COMPONENTS]
)
STATIC_NAMES = ([f'family_{f}' for f in ('HH', 'EH', 'HN', 'HL', 'EN', 'unknown')]
                + [v for n in ('station_elevation_m', 'station_vs_30_mps') for v in (n, n+'_missing')]
                + [f'{c}_{s}' for c in COMPONENTS for s in (
                    'response_missing', 'log10_sensitivity', 'velocity', 'acceleration',
                    'log1p_sensitivity_frequency_hz', 'sensitivity_frequency_hz_missing',
                    'log1p_native_sample_rate_hz', 'native_sample_rate_hz_missing')])
DIAGONAL_NAMES = ([f'noise_native_log10_rms_{c}' for c in COMPONENTS]
                  + [f'log10_prefix_noise_rms_ratio_{c}' for c in COMPONENTS]
                  + [f'noise_band_{c}_{lo}_{hi}' for c in COMPONENTS for lo, hi in BANDS])
CROSS_NAMES = ([f'{s}_correlation_{COMPONENTS[i]}{COMPONENTS[j]}'
                for s in ('noise', 'prefix') for i, j in PAIRS]
               + [f'prefix_lag_correlation_{COMPONENTS[i]}{COMPONENTS[j]}_{lag}'
                  for i, j in PAIRS for lag in (-5, 5)]
               + [f'log1p_generalized_eigenvalue_{i}' for i in range(3)]
               + [f'principal_outer_{COMPONENTS[i]}{COMPONENTS[j]}'
                  for i, j in zip(*np.triu_indices(3))])
FEATURE_NAMES = BASE_NAMES + STATIC_NAMES + DIAGONAL_NAMES + CROSS_NAMES
INVALID_CODES = {'short_segment': 1, 'nonfinite': 2, 'invalid_gain': 4,
                 'mixed_or_unknown_units': 8, 'variance_floor': 16,
                 'undefined_lag_correlation': 32, 'numerical_covariance': 64}


class InvalidObservation(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason
        self.code = INVALID_CODES[reason]


def normalized_bands(x, epsilon=0.):
    frequency = np.fft.rfftfreq(x.shape[-1], .01)
    power = np.abs(np.fft.rfft(x, axis=-1))**2
    denominator = np.maximum(power.sum(-1, keepdims=True), epsilon)
    if np.any(denominator <= 0):
        raise InvalidObservation('variance_floor')
    power = power / denominator
    bands = np.stack([power[:, (frequency >= lo) & (frequency < hi)].sum(-1)
                      for lo, hi in BANDS], -1).ravel()
    return frequency, power, bands


def prefix51(counts):
    """Same 51 formulas as feature_residual.prefix_features, in float64 raw counts."""
    x = np.asarray(counts, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] != 3 or x.shape[1] < 4:
        raise ValueError('Expected a 3-channel prefix of at least 4 samples')
    x = x - x.mean(-1, keepdims=True)
    eps = 1e-12
    rms = np.sqrt(np.mean(x*x, -1) + eps)
    peak = np.max(np.abs(x), -1) + eps
    amplitude = np.concatenate([np.log10(rms), np.log10(peak), np.log10(np.mean(np.abs(x), -1)+eps)])
    quarters = np.stack([np.sqrt(np.mean(q*q, -1)+eps) for q in np.array_split(x, 4, axis=-1)], -1)
    growth = np.minimum(quarters/rms[:, None], 10).ravel()
    frequency, power, bands = normalized_bands(x, eps)
    centroid = np.sum(power*frequency/50, -1)
    entropy = -np.sum(power*np.log(np.maximum(power, eps)), -1)/np.log(power.shape[-1])
    crossings = np.mean(x[:, :-1]*x[:, 1:] < 0, -1)
    roughness = np.minimum(np.sqrt(np.mean(np.diff(x, axis=-1)**2, -1))/rms, 10)
    crest = np.minimum(peak/rms, 30)
    return np.concatenate([amplitude, growth, bands, centroid, entropy, crossings, roughness, crest])


def masks():
    result = {}
    for arm, stop in [('B', 85), ('D', 106), ('F', 127)]:
        mask = np.zeros(127, dtype=bool)
        mask[:stop] = True
        result[arm] = mask
    return result


def describe(segment, sensitivities, units, static, seconds):
    """segment begins exactly P−200; suffix beyond each deadline is untouched.

    Returns all127 inputs and an eigenvector-degeneracy flag. The caller masks
    B/D/F only after fit-only normalization; invalid rows are shared by arms.
    """
    if seconds not in (1, 3, 5):
        raise ValueError('Only fixed 1/3/5 second deadlines are supported')
    if np.ndim(segment) != 2 or np.shape(segment)[0] != 3 or np.shape(segment)[1] < 200+100*seconds:
        raise InvalidObservation('short_segment')
    # Slice before conversion or any finite/variance check: later NaNs do not
    # change earlier validity. No global segment normalizer is permitted here.
    observed = np.asarray(segment[:, :200+100*seconds], dtype=np.float64)
    gain = np.asarray(sensitivities, dtype=np.float64)
    static = np.asarray(static, dtype=np.float64)
    if gain.shape != (3,) or not np.isfinite(gain).all() or (gain <= 0).any():
        raise InvalidObservation('invalid_gain')
    if len(units) != 3 or len(set(units)) != 1 or units[0] not in ('m/s', 'm/s^2'):
        raise InvalidObservation('mixed_or_unknown_units')
    if static.shape != (34,):
        raise ValueError('Expected the fixed34 static descriptors')
    if not np.isfinite(observed).all() or not np.isfinite(static).all():
        raise InvalidObservation('nonfinite')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            native = observed/gain[:, None]
            noise = native[:, :200] - native[:, :200].mean(-1, keepdims=True)
            signal = native[:, 200:] - native[:, 200:].mean(-1, keepdims=True)
            nrms = np.sqrt(np.mean(noise*noise, -1))
            srms = np.sqrt(np.mean(signal*signal, -1))
            if (nrms <= 1e-12).any() or (srms <= 1e-12).any():
                raise InvalidObservation('variance_floor')
            _, _, noise_bands = normalized_bands(noise)
            diagonal = np.concatenate([np.log10(nrms), np.log10(srms/nrms), noise_bands])
            cn = noise @ noise.T/noise.shape[1]
            cs = signal @ signal.T/signal.shape[1]
            correlation = np.array([c[i, j]/np.sqrt(c[i, i]*c[j, j])
                                    for c in (cn, cs) for i, j in PAIRS])
            lag_values = []
            for i, j in PAIRS:
                for lag in (-5, 5):
                    a, b = ((signal[i, -lag:], signal[j, :lag]) if lag < 0
                            else (signal[i, :-lag], signal[j, lag:]))
                    denominator = np.sqrt(np.dot(a, a)*np.dot(b, b))
                    if denominator <= 0:
                        raise InvalidObservation('undefined_lag_correlation')
                    lag_values.append(np.dot(a, b)/denominator)
            regular = cn + .01*np.trace(cn)/3*np.eye(3)
            chol = np.linalg.cholesky(regular)
            q = np.linalg.solve(chol, cs)
            q = np.linalg.solve(chol, q.T).T
            eigenvalues = np.linalg.eigvalsh((q+q.T)/2)
            if eigenvalues[0] < -1e-10*max(1., eigenvalues[-1]):
                raise InvalidObservation('numerical_covariance')
            generalized = np.log1p(np.maximum(eigenvalues, 0))
            values, vectors = np.linalg.eigh(cs)
            degenerate = bool(values[-1]-values[-2] <= 1e-6*values[-1])
            outer = np.zeros(6) if degenerate else np.outer(vectors[:, -1], vectors[:, -1])[np.triu_indices(3)]
            cross = np.concatenate([correlation, lag_values, generalized, outer])
            result = np.concatenate([prefix51(observed[:, 200:]), static, diagonal, cross])
    except (FloatingPointError, np.linalg.LinAlgError) as error:
        raise InvalidObservation('numerical_covariance') from error
    if result.shape != (127,) or not np.isfinite(result).all():
        raise InvalidObservation('nonfinite')
    return result, degenerate
