"""CPU-only synthetic prefix-likelihood preflight. No real data or training.

The complete-template controls are intentionally misspecified. Toy sensor filters
and Gaussian noise do not validate a real EEW model or establish novelty.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import sys
from pathlib import Path
import time

import numpy as np

PROTOCOL_SHA256 = '511f8678157e6d36f24ab79a79361755fd61bbc0ca74c2bb8acf528a6e1955a9'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def logsumexp(x, axis=-1, keepdims=False):
    maximum = np.max(x, axis=axis, keepdims=True)
    result = maximum + np.log(np.exp(x - maximum).sum(axis=axis, keepdims=True))
    return result if keepdims else np.squeeze(result, axis=axis)


def product(a, b):
    """Explicit matrix contraction avoids local Accelerate matmul warning flags.

    numpy_matmul_probe.json records agreement with math.fsum <=1.8e-15.
    No floating-point warnings are suppressed; no BLAS optimization is requested.
    """
    return np.einsum('ij,jk->ik', a, b, optimize=False)


def source_history(durations, sample_rate, n):
    """Causal deterministic moment-rate shapes, samples at0,dt,...,(n-1)dt."""
    durations = np.asarray(durations, dtype=float)
    t = np.arange(n, dtype=float)[:, None] / sample_rate
    return np.maximum(np.minimum(t, durations[None] - t), 0) ** 2


def lowpass(x, tau, sample_rate):
    """First-order causal low-pass with a fixed zero initial state."""
    alpha = math.exp(-1 / (sample_rate * tau))
    y = np.empty_like(x, dtype=float)
    state = np.zeros(x.shape[1:], dtype=float)
    for i in range(len(x)):
        state = alpha * state + (1-alpha) * x[i]
        y[i] = state
    return y


def sensor_transform(x, sensor, sample_rate):
    if sensor['difference_order'] == 1:
        x = np.diff(x, axis=0, prepend=np.zeros_like(x[:1])) * sample_rate
    elif sensor['difference_order'] != 0:
        raise ValueError('Unsupported derivative order')
    return sensor['sensitivity'] * lowpass(x, sensor['lowpass_tau_seconds'], sample_rate)


def causal_matrix(impulse):
    index = np.arange(len(impulse))
    lag = index[:, None] - index[None]
    return np.where(lag >= 0, impulse[np.maximum(lag, 0)], 0.)


def noise_operator(n, sensor, settings):
    """No duration/magnitude argument: noise law is shared by all hypotheses."""
    fs = settings['sample_rate_hz']
    alpha = math.exp(-1 / (fs * settings['physical_noise_ar_tau_seconds']))
    # AR state is alpha*state + innovation, with zero initial state.
    ar_impulse = alpha ** np.arange(n, dtype=float)
    return causal_matrix(sensor_transform(ar_impulse, sensor, fs))


def spectral_basis(n, frequencies, extended_length=None):
    """Real Fourier rows; extended rows intentionally sum unseen future in a control."""
    if frequencies < 1 or 2*frequencies >= n:
        raise ValueError('Frequency basis must stay strictly below Nyquist')
    j = np.arange(n if extended_length is None else extended_length, dtype=float)
    rows = [np.ones(len(j)) / np.sqrt(n)]
    for k in range(1, frequencies+1):
        rows.extend([np.sqrt(2/n)*np.cos(2*np.pi*k*j/n),
                     np.sqrt(2/n)*np.sin(2*np.pi*k*j/n)])
    return np.asarray(rows)


def projected_covariance(n, basis, sensor, settings):
    operator = noise_operator(n, sensor, settings)
    projected = product(basis, operator)
    covariance = settings['physical_noise_innovation_sd']**2 * (product(projected, projected.T))
    covariance += settings['count_noise_sd']**2 * (product(basis, basis.T))
    return (covariance + covariance.T) / 2


def gaussian_logpdf(data, means, covariance):
    """All observations x all means, with the determinant included."""
    data, means, covariance = map(np.asarray, (data, means, covariance))
    if data.ndim != 2 or means.ndim != 2 or data.shape[1] != means.shape[1]:
        raise ValueError('Invalid data/mean shape')
    d = data.shape[1]
    if covariance.shape != (d,d) or not np.isfinite(covariance).all():
        raise ValueError('Invalid covariance shape/value')
    if not np.allclose(covariance, covariance.T, atol=1e-12, rtol=0):
        raise ValueError('Asymmetric covariance')
    cholesky = np.linalg.cholesky(covariance)  # No silent jitter or fitted noise.
    difference = data[:,None,:] - means[None,:,:]
    whitened = np.linalg.solve(cholesky, difference.reshape(-1,d).T).T
    quadratic = (whitened**2).sum(1).reshape(len(data),len(means))
    logdet = 2*np.log(np.diag(cholesky)).sum()
    return -.5*(quadratic + logdet + d*np.log(2*np.pi))


def likelihood_and_posterior(data, templates, covariance, gains, gain_prior, source_prior):
    """Exactly marginalize finite gain nuisance; source prior is applied once."""
    gains, gain_prior, source_prior = map(np.asarray, (gains,gain_prior,source_prior))
    if (gain_prior <= 0).any() or (source_prior <= 0).any():
        raise ValueError('Priors must be strictly positive')
    if not np.isclose(gain_prior.sum(),1) or not np.isclose(source_prior.sum(),1):
        raise ValueError('Priors must be normalized')
    means = templates[:,None,:] * gains[None,:,None]
    conditional = gaussian_logpdf(data,means.reshape(-1,means.shape[-1]),covariance)
    conditional = conditional.reshape(len(data),len(templates),len(gains))
    likelihood = logsumexp(conditional + np.log(gain_prior)[None,None,:],axis=2)
    joint = likelihood + np.log(source_prior)[None,:]
    joint -= joint.max(axis=1,keepdims=True)
    log_posterior = joint - logsumexp(joint,axis=1,keepdims=True)
    if not np.isfinite(log_posterior).all():
        raise ValueError('Nonfinite posterior')
    probability = np.exp(log_posterior)
    if np.max(np.abs(probability.sum(1)-1)) > 1e-12:
        raise ValueError('Posterior normalization failed')
    return likelihood,log_posterior


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    index = np.searchsorted(np.cumsum(weights[order])/weights.sum(),q,side='left')
    return float(values[order[min(index,len(order)-1)]])


def weighted_cvar(values, weights, fraction=.05):
    """Top fraction by mass, including a fractional boundary record."""
    order = np.argsort(values)[::-1]
    weights = weights[order]/weights.sum()
    before = np.r_[0.,np.cumsum(weights)[:-1]]
    used = np.minimum(weights,np.maximum(fraction-before,0))
    return float((used*values[order]).sum()/fraction)


def scores(log_p, magnitude, labels, weights):
    p = np.exp(log_p)
    cdf = np.cumsum(p,1)
    truth = magnitude[labels]
    mean = np.einsum('ij,j->i',p,magnitude,optimize=False)
    quantiles = [magnitude[np.minimum((cdf < q).sum(1),len(magnitude)-1)] for q in (.05,.5,.95)]
    mean_error, median_error = np.abs(mean-truth),np.abs(quantiles[1]-truth)
    distance = np.abs(magnitude[:,None]-magnitude[None,:])
    crps = (p*np.abs(magnitude[None,:]-truth[:,None])).sum(1)-.5*np.einsum('bi,ij,bj->b',p,distance,p)
    w = weights/weights.sum()
    tail = truth >= 5
    return {'categorical_nll':float(-np.sum(w*log_p[np.arange(len(labels)),labels])),
            'crps':float(np.sum(w*crps)), 'mean_mae':float(np.sum(w*mean_error)),
            'mean_medae':weighted_quantile(mean_error,w,.5),
            'median_mae':float(np.sum(w*median_error)), 'median_medae':weighted_quantile(median_error,w,.5),
            'cvar95_mean':weighted_cvar(mean_error,w),
            'interval90_coverage':float(np.sum(w*((quantiles[0] <= truth)&(truth <= quantiles[2])))),
            'interval90_width':float(np.sum(w*(quantiles[2]-quantiles[0]))),
            'tail_mean_mae':float(np.sum(w[tail]*mean_error[tail])/w[tail].sum()) if tail.any() else None}


def run(protocol_path, output):
    if sha256(protocol_path) != PROTOCOL_SHA256:
        raise ValueError('Protocol differs from prespecified hash')
    settings = json.loads(Path(protocol_path).read_text())
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    fs = settings['sample_rate_hz']
    durations = np.asarray(settings['source_durations_seconds'])
    magnitudes = 4+2*np.log10(durations/2)
    source_prior = 10**(-magnitudes)
    source_prior /= source_prior.sum()
    gains = np.asarray(settings['gain_nuisance_values'])
    gain_prior = np.asarray(settings['gain_nuisance_probabilities'])
    max_n = int(fs*max(settings['deadlines_seconds']))
    horizon_n = int(fs*settings['template_horizon_seconds'])
    # Hypothesis templates may contain the full deterministic history; only the
    # intentionally invalid complete-template arms use its future coefficients.
    path_signal = lowpass(source_history(durations,fs,horizon_n),settings['path_lowpass_tau_seconds'],fs)
    labels = np.repeat(np.arange(len(durations)),settings['replicates_per_duration_per_seed'])
    population_weights = source_prior[labels]/settings['replicates_per_duration_per_seed']
    report = {'settings':settings,'protocol_sha256':PROTOCOL_SHA256,'code_sha256':sha256(__file__),
              'magnitudes':magnitudes.tolist(),'source_prior':source_prior.tolist(),
              'runtime':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
                         'cpu_threads_environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS')}},
              'tests_sha256':sha256(Path(__file__).with_name('test_preflight.py')),
              'results':{},'null_checks':{},'operator_checks':{},'artifacts':{},
              'scope':'Toy conditional Gaussian physical-noise simulation. No real EEW performance/novelty inference.'}
    for seed in settings['replicate_seeds']:
        rng = np.random.default_rng(seed)
        true_gain_indices = rng.choice(len(gains),size=len(labels),p=gain_prior)
        # Shared raw innovations pair sensors and nested deadlines; no future
        # innovation can affect a prefix because every operator is lower triangular.
        physical_innovations = rng.normal(size=(max_n,len(labels)))
        count_innovations = rng.normal(size=(max_n,len(labels)))
        for sensor in settings['sensor_models']:
            signal = sensor_transform(path_signal,sensor,fs)
            noise_op = noise_operator(max_n,sensor,settings)
            waveforms = signal[:max_n,labels]*gains[true_gain_indices][None,:]
            waveforms += settings['physical_noise_innovation_sd']*product(noise_op,physical_innovations)
            waveforms += settings['count_noise_sd']*count_innovations
            for deadline in settings['deadlines_seconds']:
                n = int(fs*deadline)
                basis = spectral_basis(n,settings['spectral_positive_frequencies'])
                data = product(basis,waveforms[:n]).T
                prefix = product(basis,signal[:n]).T
                complete = product(spectral_basis(n,settings['spectral_positive_frequencies'],horizon_n),signal).T
                covariance = projected_covariance(n,basis,sensor,settings)
                operator_key = f'{sensor["name"]}_{deadline}s'
                scale = np.sqrt(np.diag(covariance))
                correlation = covariance/np.outer(scale,scale)
                direct = sensor_transform(lowpass(source_history(durations,fs,n),settings['path_lowpass_tau_seconds'],fs),sensor,fs)
                prefix_error = float(np.max(np.abs(signal[:n]-direct)))
                covariance_prefix_error = float(np.max(np.abs(noise_op[:n,:n]-noise_operator(n,sensor,settings))))
                if max(prefix_error,covariance_prefix_error) > 1e-12:
                    raise ValueError('Causal observation operator failed prefix identity')
                report['operator_checks'][operator_key] = {'source_prefix_max_error':prefix_error,
                    'noise_operator_prefix_max_error':covariance_prefix_error,
                    'maximum_abs_offdiagonal_correlation':float(np.max(np.abs(correlation-np.eye(len(basis))))),
                    'minimum_covariance_eigenvalue':float(np.linalg.eigvalsh(covariance).min())}
                saved_logp = []
                null = durations > 2*deadline
                for arm in settings['candidate_models']:
                    template = prefix if arm.startswith('prefix') else complete
                    cov = covariance if arm.endswith('full') else np.diag(np.diag(covariance))
                    likelihood, log_p = likelihood_and_posterior(data,template,cov,gains,gain_prior,source_prior)
                    saved_logp.append(log_p)
                    key = f'seed{seed}_{sensor["name"]}_{deadline}s_{arm}'
                    report['results'][key] = {'population':scores(log_p,magnitudes,labels,population_weights),
                        'balanced':scores(log_p,magnitudes,labels,np.ones(len(labels))),
                        'per_duration':{str(d):scores(log_p[labels==i],magnitudes,labels[labels==i],np.ones((labels==i).sum())) for i,d in enumerate(durations)}}
                    null_likelihood = likelihood[:,null]
                    lr_difference = float(np.max(np.abs(null_likelihood-null_likelihood[:,:1])))
                    # Condition the hypothesis family before normalization. This
                    # avoids subtracting enormous, nearly equal negative log
                    # posteriors when that entire family has negligible mass.
                    null_joint = null_likelihood-null_likelihood.max(1,keepdims=True)+np.log(source_prior[null])[None,:]
                    null_logp = null_joint-logsumexp(null_joint,axis=1,keepdims=True)
                    expected = source_prior[null]/source_prior[null].sum()
                    posterior_error = float(np.max(np.abs(np.exp(null_logp)-expected[None,:])))
                    report['null_checks'][key] = {'null_durations':durations[null].tolist(),
                        'likelihood_ratio_log_max_abs':lr_difference,
                        'conditional_null_posterior_vs_prior_max_abs':posterior_error,
                        'role':'required_identity' if arm.startswith('prefix') else 'intentional_negative_control'}
                    if arm.startswith('prefix') and (lr_difference>1e-10 or posterior_error>1e-12):
                        raise ValueError('Causal null leaks final magnitude')
                artifact = output/f'seed{seed}_{sensor["name"]}_{deadline}s.npz'
                np.savez_compressed(artifact,log_probability=np.stack(saved_logp),
                    arms=np.array(settings['candidate_models']),labels=labels,magnitudes=magnitudes,
                    true_gain_indices=true_gain_indices,source_prior=source_prior,observed_coefficients=data,
                    covariance=covariance,prefix_templates=prefix,complete_templates=complete)
                report['artifacts'][artifact.name] = {'sha256':sha256(artifact),'bytes':artifact.stat().st_size}
                if sum(item['bytes'] for item in report['artifacts'].values()) > 1024**3:
                    raise RuntimeError('Prespecified 1GiB output bound exceeded')
                if time.monotonic()-started>900:
                    raise RuntimeError('Prespecified15-minute simulation bound exceeded')
    report['wall_seconds'] = time.monotonic()-started
    report['status'] = 'complete'
    (output/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol',default='protocol.json')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    result = run(args.protocol,args.output)
    print(json.dumps({'status':result['status'],'wall_seconds':result['wall_seconds'],
                      'conditions':len(result['results']),'output':args.output}))
