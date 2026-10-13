# Independent L numerical core V1

Prospective source-only NumPy/SciPy library. No Torch, producer, AR kernel, model, IO, cloud, optimizer or execution-authority imports. No actual arrays/weights/results used. Does not decide42 guards or authorize fits; the separate future full auditor/controller must bind source/native/initialization/history/custody and independently reconstruct the static prior.

Load proper_core then ar_core under positively verified unique source aliases; ar_core.p must identify that exact proper_core module. proper_core.py is a byte-identical copy of the frozen independent S/P/D auditor V2 math_core.py (SHA256 d805dbccfcae42cd0867581a677f8e2b9d6531ccfe7b2c616b5f7bf73c7df6ca). It supplies unchanged all-real mixture scoring, operation-aware prior-forward helpers and rejection rules; its old S/P completion is used only as a null-test comparator.

## Public API

- Budget(processing_begin) aliases the existing10s/1M-point budget. Caller must start the clock before any record processing. Every API requires the same budget object; duck objects supporting tick() and charge(points,terms) are accepted. Returned Mixture keeps that object. No implicit budget reset inside L reconstruction.
- build_reference(prior, marks, coefficients, nu, mref, horizon, arrival_offset_ns, *, budget) -> dictionary below. prior is tuple/list3 float64 C-contiguous[5] arrays(logweights,means,scales); marks float64[J,3]; coefficients float64[3,6] ordered a,b,d,e,rho,rawsigma; nu float64[12,3]. Scalar mref finite abs<=1e6. Horizon builtinint1/3/5, offset builtinint0..750000000ns; J=floor((h*1e9-offset)/250000000). All input statistical arrays finite abs<=1e6, scales>=.05, logweight normalizer<=1e-12, all marks strictly>-12. Copies inputs into evidence.
- complete(reference, budget) -> Mixture. Independently re-derives the clock/count/lags/loadings before completing all factors; never trusts a supplied loading. Recomputes from the original prefix prior once, with12 shared supports outside the product; no suffix API/redrawn nuisance.
- verify_source(source, prior, marks, coefficients, nu, mref, horizon, arrival_offset_ns, prior_bounds, *, budget) -> independently reconstructed Mixture. Inputs must originate from independently bound native data and checkpoint-forward reconstruction, not from source.reference. prior_bounds is tuple/list3 float64[5] nonnegative error arrays from that independent reconstruction. Source fields are compared to independently derived evidence, with exact coefficient/rho/nu/observed-lag/clock agreement and operation-aware affine/loading/prior bounds.

Mixture exports logw,mu,sd,logz,noise (60 components; noise[12]) and mean(),nll(target),cdf(x),quantile(q),crps(target),integral_crps(target),scores(target,crosscheck=True,evidence=None). scores gives mean,median,nll,crps,pit,quantiles seven keys0.025/0.1/0.25/0.5/0.75/0.9/0.975 and inclusive Boolean coverage50/80/95. CDF-integral CRPS includes infinite tails; no magnitude truncation. Caller retains partial evidence on exceptions and applies frozen final forecast comparisons; this core does not validate custody, diagnostics or producer-reported aggregate success.

## Exact source ABI

Outer source exactly: reference, log_weights[60], means[60], scales[60], log_normalizer builtinfloat, noise_probabilities[12].

Reference exactly: arm='L', prior(list3 arrays[5]), coefficients[3,6], rho[3], nu[12,3], mref builtinfloat, horizon builtinint, arrival_offset_ns builtinint, count builtinint, last_observed[3], facts(listJ). Prior denotes current model weights evaluated at the fixed static prefix context, not original optimizer-initial weights. Initial-training provenance belongs to the future full auditor.

Each fact exactly: cell(zero-based builtinint), intercept[3], slope[3], sigma[3], value[3], previous[3], loading[3]. First previous=zeros and loading=ones; later previous=observed preceding mark and loading=1-rho. Time covariate is log1p(.25*cell); sigma=.05+softplus(rawsigma), strict threshold>20 linear. The conditional mean rho derivative later is previous-nu. No new rho restriction; loading may be zero/negative.

Completion uses centered all-factor precision/information, determinant and residual-square terms,12 uniform shared support weights, then normalizes all60 components in noise-major/prior-minor order. Existing ULP/lognormalizer/posterior-mean/NLL representation failures remain terminal, never rounded or clipped. Loading subtraction/product uncertainty is propagated into the inherited information/mean arithmetic bound. Bounds are conservative operational float64/libm checks, not a formal transcendental certificate. The separate80-digit Decimal direct-normal-equation oracle is test-only. It derives the law from primitive inputs without importing this core.

Source mixture arrays use the inherited1e-10*(1+abs(expected)) agreement, logZ<=1e-4. Future full forecast verification retains mean/NLL<=1e-4, CDF/CRPS/median/sevenquantiles<=1e-6 and exact inclusive coverage. Do not enlarge these tolerances based on actual values. No uncertainty calibration, physical identification, EEW accuracy or novelty claim follows from these checks.

## Verification

python3 -B -m unittest discover -s . -p test_ar_core.py -v

28 invented tests cover independent Decimal completion at1/3/5, rho0 fixed-parameter S identity (not a rho-gradient identity), zero-nu P marginal, first-cell identity, rho1/negative loadings, latent-level translation, conditional-mean and NLL rho derivatives, uninformative-amplitude prior identity,60-component order, copied-prefix causality, proper-score/integral/quantile/coverage checks, actual source mismatch rejection, input domains, unresolved numeric bounds, normalization and budget rejection, preserved rejected-NLL bit evidence and absence of producer/Torch imports. Translation of marks and nuisance is an algebraic fixture, not an authorized transformation of empirical support.

Production minimum is ar_core.py and unchanged proper_core.py. decimal_fixture.py/test_ar_core.py are invented-fixture verification only. Frozen L protocol remains controlling; source-only tests are not actual data admission or independent outcome verification.
