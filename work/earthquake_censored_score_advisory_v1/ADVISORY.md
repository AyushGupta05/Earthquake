# One prospective distribution-training ablation after L

Authored 15 October 2026. Source-only advisory; no implementation, fit, data acquisition or permission to launch. This does not alter the frozen L study. No private datasets, metadata, forecasts, weights or account records were opened. The supplied negative S/P/D summary is motivation, not evidence used to select a hyperparameter. No new DEV outcomes were consulted.

**Recommendation:** retain the existing direct distributional D estimator and test one established objective: ordinary magnitude NLL plus an upper-tail censored-log score, with threshold fixed at **Mw >= 5.5** and coefficient fixed at **one**. Compare against D and an otherwise identical doubled-NLL control. This is a modest proper-score engineering ablation, not a new foundational method. It adds no waveform information; its only possible benefit is a different finite-model training compromise.

## The hypothesis and its exact limits

Let q_theta(m | x_h) be D's normalized all-real magnitude density at the original h=1/3/5 second deadline. Define c=5.5 and q_0=Pr_q(M<c | x_h). Use loss (smaller is better)

```
N(q,y) = -log q(y | x_h)
C(q,y) = -1[y >= c] log q(y | x_h)
         -1[y <  c] log q_0(x_h)
L_C(q,y) = N(q,y) + C(q,y).
```

Thus a tail label contributes twice its density NLL; every lower label also contributes the negative log probability of being below c. That second term matters. Merely doubling high-label NLL instead minimizes a label-tilted distribution in an unrestricted model. Here the extra term scores the actual tail incidence as well as tail density. This is **censoring in an added scoring rule**, not censoring the available labels, observing rupture arrest, or changing the waveform measurement law.

Our algebra: for a true continuous conditional density p, let p_0=Pr_p(M<c), and T_c map every lower outcome to one symbol while retaining each upper outcome. Conditional expected excess loss is

```
E_p[L_C(q,Y)-L_C(p,Y) | x]
  = KL(p || q) + KL(T_c p || T_c q) >= 0.
```

The first term retains strict identification of the whole density under the usual support/integrability assumptions. This population identity neither guarantees calibration in a finite sample nor protects bulk MAE, MedAE, CVaR95 or maximum error under a restricted D model. It also does not guarantee rare-event MAE improvement. The primary point action remains the original distribution mean.

Equality convention is explicit: **y=5.5 belongs to the upper branch**, matching evaluation. q_0=F_q(c-) and for D's continuous mixture this equals F_q(c); do not use a discontinuous >5.5 training rule with a >=5.5 gate. For genuinely rounded/discrete catalogue labels, continuous density NLL is a working likelihood and the displayed continuous-density propriety claim is not a theorem for the observed discrete law. Keep D's existing target representation in all arms and disclose this limitation. An interval/discrete likelihood would require a separately frozen shared precision model and all-arm comparison; it is not silently added here.

The scientifically testable failure hypothesis is that a small restricted density estimator allocates too little fitting precision to upper-tail density and incidence. The public D schema permits a summary-dependent common mean shift and one variance-scale coefficient, retaining the static prior's mixture weights. This objective cannot turn that restriction into a new waveform-conditioned tail-mixture gate. D may already be the better compromise; the extra score can overfit a few events, shrink mixture scales, move means upward, or degrade ordinary errors. No new separating information is manufactured when early prefixes overlap.

## Why this candidate, rather than repeating a named mechanism

| Close precedent / exhausted direction | Consequence for this advisory |
|---|---|
| Diks, Panchenko & van Dijk, 2011; author working paper dated 19 May 2008, Eq.11 | The censored-log construction is established. The recommendation specializes its upper-tail version as a training addition; no score novelty is claimed. [Journal DOI](https://doi.org/10.1016/j.jeconom.2011.04.001), [institutional author manuscript](https://research.vu.nl/ws/files/73350530/08050). |
| TEAM-LM, arXiv v2 14 April 2021, §2.2 and §4.5 | Already uses five-component magnitude MDNs and likelihood training, with temporal blinding and large-event oversampling; discusses miscalibration. D's mixture, distributions and causal updating are not a novelty claim. [Primary text](https://arxiv.org/html/2101.02010v2). |
| Münchmeyer, Leser & Tilmann, arXiv v1 16 March 2022, Appendices B–D | Already trains Gaussian-mixture magnitude forecasts with CRPS, addresses future rupture uncertainty, and derives an upsampling correction. Switching D to a distributional/proper score is occupied. Their own-P teleseismic windows differ from a common network deadline. [Primary text](https://arxiv.org/html/2203.08622v1). |
| A2MAG, published 29 June 2026; accepted manuscript pp.27–29 | Uses MSE sequence-map training and a single-station three-post-P-second test geometry. It is not evidence for this proper density objective or matched 1/3/5-second performance. Its 10-second post-P SNR selection cannot become an online admission rule here. [Publisher](https://www.nature.com/articles/s44304-026-00242-3), [accepted manuscript](https://www.nature.com/articles/s44304-026-00242-3_reference.pdf). |
| Böse & Heaton, 2010, Bayesian method; existing rupture-survival ledger | Remaining-rupture distributions conditioned on present slip are longstanding; local waveform plateau is not observed rupture arrest. The proposed score carries no survival-state interpretation. [Primary paper](https://academic.oup.com/gji/article/183/2/1014/650713). |
| Existing `INSTRUMENT_PROPER_SCORES.md` | Already specifies binned CRPS, tail/marginal weighted CRPS and ranked-log controls. This advisory is not a revival of those as a new principle. The narrower unresolved comparison is censored-log training on the admitted continuous direct D. A bounded documentation search found no such exact arm; this is not an exhaustive implementation claim. |

Gneiting–Ranjan threshold-weighted CRPS also preserves propriety while emphasizing thresholds; the older project controls cover that family. [2011 primary manuscript](https://citeseerx.ist.psu.edu/document?doi=07b14f69099d1fdab8f09ff4e4155f379a5fcd8d&repid=rep1&type=pdf). The choice here avoids a fresh CRPS scale/bandwidth grid and exposes one explicit tail-incidence correction.

Conditional noise/entropy weighting was considered and not selected. A **fixed positive input-only** weight w(x) on NLL preserves its unrestricted conditional minimizer, but reallocates finite-model capacity and can prioritize irreducible noisy inputs. A model-dependent entropy weight with gradients through it is a different objective and need not retain that argument. Variance-weighted likelihood training already has primary precedent in beta-NLL; it is not new evidence about rare earthquakes. [Seitzer et al., ICLR 2022 paper](https://openreview.net/pdf?id=aPOpXlnV1T), [official code](https://github.com/martius-lab/beta-nll). A risk-weighted magnitude objective is also different from estimating the natural density: neither proper scores nor CVaR objectives guarantee simultaneous improvement in all requested point errors.

## Prospectively fixed comparison, if separately admitted

This is a design specification only. Four new fits would suffice: two seeds for the candidate and two for its scale control, reusing the independently closed D and B/F/H/T comparators. Do not choose the best of B/F/H/T after seeing new scores: compare with **all four**, which covers the strongest of them.

| Arm | Per-event/per-horizon objective | Everything else |
|---|---|---|
| D, reused reference | N | Original closed run |
| D2, scale control | 2N | Original D model and initialization |
| DC, candidate | N+C | Original D model and initialization |

Reuse exactly the admitted common 65 TRAIN / 22 DEV cohort, original namespaces, static-30 TRAIN constant/rank mask and scalers, D's active summary mask, native/prefix/clock/packet identity and original genuine capacity. Do not assume D has S/P's architecture; no new parameter or support component is introduced. Inherit the admitted q<=17 and <=5% genuine-capacity limits, not dummy padding. No refetch, new quality cut, dropped event, new feature or alternative fold. TEST remains sealed.

For each of seeds 20261012 and 20261013, start DC and D2 from the **same original untrained D admission state**, never a trained D/S/P/L checkpoint. Reuse original seed+1009 orders: eight distinct TRAIN events per update, all three horizons, 24 separate B=1 losses/backwards divided by 24 in the original accumulation order. Use 300 updates, fresh Adam(lr=.001, weight_decay=0), gradient norm cap five, float64 CPU and the original deterministic runtime. Final checkpoint only; no DEV stopping, temperature, coefficient, threshold, label-noise, oversampling or epoch search. Keep natural uniform-event contribution unchanged. All fitting, constant tests and numerical diagnostics use TRAIN only.

Compute log q_0 from the exact exported complete normalized mixture with stable log-CDF/log-sum-exp arithmetic; no probability clipping, Gaussian surrogate or finite magnitude truncation. Stop for nonfinite values rather than rescuing the objective. Record unscaled N and C, clipping frequencies, order/state/source hashes and all genuine-parameter gradient admissions; the original 195-term initial/final probes remain required. Preserve source/time/resource limits rather than widening them for the new objective.

Before any real fitting, an independent source review and invented-distribution checks must verify: the reflected Eq.11 formula; the >= equality branch; lower-mass normalization; finite extreme-mixture log-CDFs; analytic/automatic gradients; lambda=0 exact D loss/gradient parity; and the binary null in which all lower outcomes are one symbol and C=N, hence DC=D2. For an invented binary truth with tail probability .1, label-weighted NLL with tail weight two targets 2/11, whereas N+C still targets .1. These are mathematical checks, not forecast results.

At each original 1/3/5-second clock, use only samples, marks, reference noise and station availability admitted by that deadline; never give every station h seconds after its own P. No new rupture-onset estimate, final duration, future SNR, future normalization or filtering state. Replay same packet with changed post-cutoff values as a causal-invariance check. No products of normalized nested-prefix posteriors are introduced.

Report both seeds separately at every horizon, DC versus D2, D and each B/F/H/T. For each of the resulting 36 fixed comparisons, require >=.02 improvement in Mw>=5.5 MAE and no worsening in whole MAE/MedAE, lower-Mw MAE/MedAE, CVaR95 absolute error and maximum absolute error. Require strictly lower ordinary natural-event NLL and CRPS against D2, D, B and F; H/T proper scores retain the inherited diagnostic status. Mean action stays primary; median-action errors, Mw>=6, bias, tail probabilities, PIT/coverage and every individual-event delta are diagnostic. Missing strata or an incomplete numerical/audit record means incomplete, not a pass. Keep any confidence-interval/bootstrap procedure fixed from the original comparison; no resampled winner selection or failed-horizon averaging.

Mechanistic support requires DC to improve on **D2**, not only D; otherwise objective scale/optimizer dynamics remain a sufficient explanation. A proper-score gain without the point-error gates is useful density evidence but fails Ayush's stated objective. A failure ends this candidate; it does not license a lambda/threshold/entropy sweep or a change to L.

Exact public/source/runtime/admission hashes must be bound in a separate final executable protocol before any fit. The advisory itself is not a runnable protocol or independent generalization evidence. Reused DEV has already influenced the research trajectory; even a clean pass is exploratory. A publication-level improvement claim requires an untouched independently held event/site/time evaluation with sufficient large-event support and matched causal baselines. No novelty, published superiority or inevitable simultaneous gain follows from this memo.
