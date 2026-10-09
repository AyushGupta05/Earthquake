# Shared-cap contrast preflight

This is a conditional density diagnostic on the already extracted **TRAIN** observations, with event-disjoint two-fold evaluation. It gives each density the true magnitude as a covariate. It does not predict magnitude, establish early-warning improvement, or identify a physical rupture state. No VAL/TEST waveform, probability, or target file is read.

`protocol.json` was fixed locally before real-data loading at 2026-10-09 20:43:19 UTC. SHA256: `92b54f5f57cec682956ce5a0e2d584292cd85a83c8d7980ce9336bdc0e282c21`. This is local prespecification, not an external registration.

The source is the pinned `train_observations.npz` from the earlier censored pilot; the runner rejects any other hash. Those observations preserve signed innovations. If `a`, `b`, `c` are the logarithms of the vertical peak in disjoint intervals [0,1), [1,3), [3,5), then the saved innovations are `(b-a, c-max(a,b))`. The diagnostic recovers `(b-a,c-a)`. A common scalar gain cancels. Frequency-dependent response, site/path effects, released full-record preprocessing, and catalogue P picks remain limitations. The source baseline uses the first ten post-P samples, not pre-P noise. Source-native floor and response-validity masks are unchanged.

Three fitted arms use the same full 2x2 residual covariance family. `shared_cap` retains a three-component mixture over an empirical shared cap offset. `moment_matched` independently optimizes the Gaussian formed from exactly the mixture family's first two moments, with the same 11 parameters, starts, weights, and optimizer. `linear_gaussian` is a coarser 7-parameter affine-mean reference. `moment_match_from_shared_cap` is a separately labelled evaluation-only counterfactual at the fitted mixture's parameters: its comparison isolates shape compression but is not a comparison with an optimized Gaussian. Both the Gaussian normalizer and determinant are included.

Two fixed optimizer initializations are retained separately; there is no held-fold model selection or ensemble. Native acceleration and velocity are separate strata. The primary fit is 5-second joint conditional NLL with inverse eligible-record event weights. At 3 seconds the first-coordinate marginal is scored, with the future coordinate deliberately replaced by NaN. At 1 second there is no contrast and the likelihood is identically one. Thus, even passing all gates would not meet the requested 1/3/5-second magnitude objective.

Run with an existing PyTorch/NumPy environment (no dependency changes needed):

```sh
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -W error::RuntimeWarning -W error::UserWarning -m unittest -v test_shared_cap.py
CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python run_preflight.py --source /mnt/eew-research/runs/censored_innovation_6c1510b97725_c9dd74d23d87/train_observations.npz --output run_20261009
```

The runner enforces the protocol/source hashes, exact identities, event-label consistency, CPU-only use, one thread, and 30-minute process alarm. Outputs include all source identities and masks, per-row held likelihoods/PIT, every fit/start and initialization hash, equal-event summaries, event-bootstrap intervals, decision gates, and SHA256 manifest. It refuses an existing output directory. A failed run retains its status and completed artifacts; no automatic retry or tuning occurs.

The null/invariance/numerical tests and actual Codex autoreview precede real fitting. The review uses an isolated snapshot with an empty baseline, never the shared project repository. Review files and final tests/results are retained alongside this README. Interpret the fitted cap parameters only as an empirical response family; sparse large-event support and optimizer convergence must accompany any conclusion.
