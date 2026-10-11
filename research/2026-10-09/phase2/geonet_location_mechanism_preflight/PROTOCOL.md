# Location integration: fixed data-free calculation

This preflight uses invented quantities, exact Gaussian-mixture conditioning and two fixed random seeds. It does not fit a model, read TRAIN/DEV/TEST data, acquire waveforms, launch AWS or establish a new method. The shortlist's arrival-only locator and correctly waveform-conditioned joint inference are distinct arms. All arms receive the same synthetic amplitude and currently available timing observations; no catalogue geometry is supplied as a prediction input.

## Observation law fixed before calculation

Use seeds 20261011 and 20261012, 4,096 invented independent events each, three snapshots labelled 1/3/5 seconds, and respectively one/two/three reported stations. This is an abstract prescribed availability schedule, not a simulation of GeoNet delivery or first-P network selection. Unknown report absence supplies no location likelihood. Origin time is free and eliminated by differences. No later observation is used in an earlier snapshot.

Two source positions are g0=(10,0) and g1=(100,0) km with equal probabilities; stations are (0,0), (0,6), (0,12) km. One shared source determines every station distance. Relative travel times are (Ri−R1)/6 seconds. The one-station timing likelihood is constant. At two/three reported stations, pick errors have marginal SD 0.12 seconds; differences to the common first pick have covariance 0.12²(I+11ᵀ). Use that same known covariance in all base arms. All these theoretical differential times are below one second; later reporting in this abstract schedule is missing/available information, not a future P-time forecast.

Magnitude has unbounded density 0.95N(3.7,0.4²)+0.05N(6.8,0.5²), independent of source position. The invented log-amplitude law is ai=M−2log10(Ri)+ηi. At the three snapshots the independent amplitude SD is 0.35/0.25/0.20, with shared zero-mean amplitude error SD 0.15. Thus Σa=σa²I+0.15²11ᵀ. Use common random event magnitudes, locations, pick errors and amplitude normal draws for every arm and horizon. Scaling the same amplitude draws across snapshots makes the calculation paired; it is not an independent-block likelihood or repeated posterior multiplication.

## Matched analytic arms

1. **Exact joint / direct oracle:** q(M,g|a,T) from the known generative law, with geometry weights updated by waveform marginal evidence. An unlimited direct flexible model with the same information and correct law can represent this identical q(M|a,T); this is an information ceiling, not a trained competitor.
2. **Arrival-only mixture:** sum_g q(g|T)q(M|a,g), matching the shortlist's timing-only geometry weights. This is normalized but generally differs from the exact joint posterior.
3. **Mean-location plug-in:** one conditional density at the coordinates E[g|T]; derive all station distances there.
4. **ElogR plug-in:** one conditional density at each station's E[log10 R_i|T]. This removes the basic Jensen confound.
5. **Arrival-mixture moment Gaussian:** a single Gaussian with the arrival-only mixture's exact mean and variance. Primary point errors must equal arm2 exactly; proper scores can differ.
6. **Independent-distance joint diagnostic:** give each station an independent source-state draw from q(g|T), enumerate the 2^n distance combinations and condition on amplitude with the same magnitude prior/noise. Marginals match arm1's pre-amplitude geometry marginals, while the common-source correlation is deliberately broken. This is a misspecified control, not a plausible physical mechanism.
7. **Joint-ElogR plug-in diagnostic:** use the exact joint geometry weights to obtain E[log R|a,T], then the same conditional magnitude density. No extra observable is added. Differences from arm1 can arise from the nonlinear conditional mean induced by the magnitude mixture prior.

All magnitude conditionals and integrations are exact finite Gaussian mixtures with normalized weights and no density floor. Proper scores are stable NLL and closed-form Gaussian-mixture CRPS. Primary decision is the distribution mean; secondary decision is its numerical median. Report event MAE, MedAE, M≥5.5 and ≥6 MAE, signed tail bias, largest error, P95 and CVaR95. No per-arm high-M reweighting or threshold tuning occurs.

## Fixed locator stress

Retain exactly the same invented events/amplitudes. Give every geometry-conditioned arm a wrong far-source prior of 0.02 and an overconfident timing-error SD 0.04 seconds. For true far-source events with M≥5.5, replace reported differential times by the near-source expectation plus their original noise. This deliberately adversarial timing/prior failure probes rare-source support and false confidence; it is not an estimate of GeoNet error frequency. The correctly specified direct oracle remains an unattainable reference, not a fair learned winner against these misspecified arms. Do not select a repair or blend after observing this stress.

## Hypotheses and gate

Verify the linear single-Gaussian conditional-mean null: integrating geometry is exactly equal to plugging E[log R] when the weights and conditional coefficients are the same. Verify moment matching changes no primary mean error. Verify the exact joint equals the direct oracle, density weights sum to one, covariance retains a shared source, and selected conjugate calculations agree with independent one-dimensional quadrature.

For the **arrival-only shortlist mechanism**, a deliberately demanding existence screen asks for at least 0.02 lower M≥5.5 and ≥6 mean-decision MAE versus ElogR plug-in at every snapshot in both seeds, with all-event MAE/MedAE increases no greater than 0.005 and CVaR95 increase no greater than 0.02. This is an invented-problem gate, not a statistical test or real-data acceptance rule. Record failure rather than modifying the toy or thresholds. Apply the same guard descriptively to the exact-joint diagnostic. A score-only gain, superiority over E[R] alone, or a gain against a control denied the locator labels/inputs does not establish the requested point-error mechanism.

Even a pass cannot show an advantage over a direct flexible model, operational robustness, novelty or a published benchmark. Any future learned claim requires shared TRAIN-only geometry labels, out-of-fold predictions, equal head capacity/updates, same direct timing/geometry inputs and a fixed independent cohort. No waveform fitting is earned by this calculation alone.
