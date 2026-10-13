# Affine-logistic all-real scorer V3 API

This new source-only package changes numerical execution, preserving the mathematical density operator. It does not authorize a new scientific run. No actual earthquake arrays, outcomes, candidate source/tests or cloud resources were read. All prior frozen source is untouched.

```python
from scorer import score, NumericalFailure
result = score(pi, mu, sigma, affine, target,
               processing_begin=parent_monotonic_begin,
               budget_seconds=10, tolerance=1e-6,
               require_gh=True, gradients=False)
```

`pi`, `mu`, `sigma` are exact builtin lists of five finite builtin int/float values (bool excluded). Weights are nonnegative, sum within1e-6 of1; standard deviations must be at least0.05, inherited from the model parameterization. Smaller sigma is rejected, never clipped. `affine` is an exact list of at most19 exact two-member finite builtin numeric lists `[intercept,slope]`. Empty factors are allowed. Magnitude is all-real, with no upper/lower magnitude cap. `target` is a finite builtin number. No tensors, model, optimizer, data loader, sampler or I/O lives in `scorer.py`.

The density is `q(x) = sum_i pi_i Normal(x;mu_i,sigma_i²) * product_j sigmoid(a_j+b_j*x) / Z`. The parent supplies a finite monotonic timestamp before imports/work. `budget_seconds` is finite in(0,10], `tolerance` in[1e-8,1e-6], flags are exact bool. Cooperative deadline checks do not prove hard process/RSS containment; the parent must separately enforce any adopted production bound. Representation, convergence, reference or GH disagreement refuses a result. Some finite mathematical inputs can be unrepresentable and fail closed. Unexpected Python/library errors also mean no accepted result.

Top-level keys: `accepted`, `diagnostic_only`, `score`, `error`, `reference_error`, `gh_error`, `gh_required`, `gradients`, `gradient_error`, `work`, `method`. `method` is `vectorized-all-real-legendre-CDF-v3`. Only `require_gh=True` can produce `accepted=True`. Explicit `require_gh=False` is diagnostic-only and always returns acceptedFalse; it is never a fallback that can promote a failed GH check.

`score` contains finite builtin floats: `log_normalizer`, `mean`, `nll`, `crps`, `median`, `pit`, `absolute_moment`, `pair_half_moment`, `cdf_product`, `coverage_50`, `coverage_80`, `coverage_95`; `quantiles` has keys `0.025`, `0.1`, `0.25`, `0.5`, `0.75`, `0.9`, `0.975`. Coverage is an inclusive scalar indicator. PIT always comes from the separate adaptive target CDF; other output values come from accepted64-point continuous quadrature. The extra moment fields expose CRPS decomposition, not extra model parameters.

`error` reports32/64 differences for logZ/mean/NLL/CRPS/median/PIT/max quantile, alternate CRPS identity difference, and internal spectral probability defect. Each score difference must be at most tolerance×(1+absolute relevant64-point score); max quantile error uses2×tolerance. Internal CDF defect is also bounded by1e-10 and is retained without clipping. `reference_error` has absolute errors for logZ,mean,NLL,CDF at the7quantiles plus target, and independently mode-seeded Eabs; each≤1e-4. `gh_error` has64/128/adaptive ranges for logZ,mean,NLL; default each≤1e-4. These are numerical diagnostics, not certified universal error bounds.

`work` contains integer vector density evaluations (≤2,000,000), independent reference evaluations (separate≤2,000,000), intervals (≤512) and refinement index (0..7). Initial cut count≤128. Rules and512intervals bound individual vector array shapes. Imports/reference/Hermite work are not included in vector evaluation count.

Optional `gradients` contains lists for softmax `logits`(5), `mu`(5), `log_sigma`(5), `intercept`(number of factors), `slope`(number of factors). These are analytic derivatives of **logZ**, evaluated with accepted quadrature;32/64 maximum difference≤1e-5. They do not differentiate adaptive interval choices or create a PyTorch autograd path, and they are not CRPS gradients. Without the flag, both gradient fields are null.

`NumericalFailure` carries a short reason via `str(error)` and optional `.evidence`. Inherited reference errors are also ValueError; any failure yields no accepted object. Callers must retain failure/denominator and cannot substitute a Gaussian, truncate support or relax checks.

`run_tests.py` runs only invented fixtures and prints a generic JSON receipt. `run_benchmarks.py` measures the fixed eight invented cases, emits separate old failures/disagreements, and includes independent diagnostic grids. Both are source/test tools, not an actual study interface. Python3.9 syntax; NumPy/SciPy are required. Local verification uses the existing Python3.14 runtime; target Linux3.9 compatibility/performance remains for the parent to verify.
