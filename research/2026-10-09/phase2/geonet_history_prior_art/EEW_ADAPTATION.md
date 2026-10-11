# A history prior with uncertain current source

The candidate new input is background catalog state, distinct from another mapping of the current waveform. The derivation below is this project's proposed inference contract; it is not an implemented or tested result. Let M be final magnitude, z be current hypocenter/origin time, W_d the strict waveform/pick prefix at an absolute deadline d, A_d the actually available station/detection information, and H_d the published background state. All densities must refer to the same detected-event population and magnitude scale/support.

Suppose an unchanged waveform model represents a joint posterior q0(M,z | W_d,A_d) under effective training prior pi0(M,z | A_d). If its conditional observation law transports to the new history, the coherent replacement is

```
qH(M,z | W_d,A_d,H_d)
  = normalize[ q0(M,z | W_d,A_d)
               * piH(M,z | A_d,H_d) / pi0(M,z | A_d) ].

qH(M | W_d,A_d,H_d) = integral qH(M,z | ...) dz.
```

The denominator removes the training prior once; it is not an extra history likelihood. It must be strictly positive on every proposed target state. Pi0 is the effective prior after cohort selection, magnitude repetitions/weights, target smearing, masks and prefix sampling, not an arbitrary stationary GR curve. A discriminative model's approximate learned posterior need not obey this identity exactly. Dependence of noise/coda/detection on history can also violate the observation-law assumption. Evidence of ratio correction under those assumptions requires testing; joint refitting on W,H is a separate alternative and must not be mislabeled exact posthoc Bayes.

A practical factorization might use piH(M,z|A,H)=pH(M|z,H,A)*rH(z|A,H). The conditional magnitude model does not by itself provide the source-occurrence/detection factor rH. To isolate magnitude-history information, first fix rH=r0 and explicitly describe that restriction. If adding a history-conditioned location/intensity factor later, compare it separately. Detection and station topology are part of this conditioning; extrapolating an unconditional regional catalog density to a detected waveform-selected population without checking that selection is unjustified.

If only a magnitude posterior q0(M|W,A) exists, the necessary identity is instead

```
qH(M|W,A,H) proportional to
  q0(M|W,A) * E[z | M,W,A under q0]
                   [ piH(M,z|A,H) / pi0(M,z|A) ].
```

An independent-looking location marginal q(z|W,A) is generally insufficient because magnitude and location trade off. Evaluate a numerical joint grid/particle approximation or a source-independent global history control. Plugging in the final catalog hypocenter/time is an oracle control only. Multiplying q0(M|W,A) by a prior averaged using the same waveform-derived location marginal is neither this expectation nor independent evidence. A plugin may be studied as an approximation, with its omitted dependence stated, but cannot certify the proposed Bayesian mechanism.

Own two-state illustration: with an uninformative waveform, pi0(high)=0.1 and piH(high)=0.2, q0 equals pi0. Correct replacement q0*piH/pi0 returns 0.2. Multiplying q0*piH and renormalizing returns 0.02/(0.02+0.72)=0.0270, pushing high probability down despite a higher history prior. This is algebra, not an earthquake experiment. Multiplying two full-prefix posteriors at successive deadlines likewise repeats both the prior and overlapping waveform evidence. For 1 to 3 to 5 seconds, either recompute the full-prefix posterior with one replacement at each deadline, or use genuinely incremental conditional likelihoods for the newly arrived suffix given the earlier prefix. A density difference can be an approximation to that increment only under stated invariance and calibration assumptions.

A conservative candidate prior is pi_alpha=(1-alpha)*pi0+alpha*piH, with alpha fixed on training/validation and alpha=0 an exact no-history control. Its ratio is (1-alpha)+alpha*piH/pi0. Alpha can reflect only prospectively available coverage/age diagnostics; it must never use the true current magnitude, final event location, late catalog revision or the observed validation error of that event. Ratio clipping, support floors and entropy gates are separate approximations to freeze and ablate, not guarantees of bulk preservation. With insufficient history return to pi0; do not invent missing events or encode a padded mock earthquake as an observation. Directly concatenating H with W is a useful matched alternative, but learning a joint model removes the claim that pi0 is exactly corrected once.

A history density learned above a catalog cutoff or on a finite magnitude interval does not automatically cover the waveform target population. Preserve full target denominators, report unsupported mass and choose a prospective fallback/mixture instead of excluding low or extremely high target events after inspection. Historical reported ML/Mw/other types and their uncertainties require an explicit training-only mapping to the final magnitude target; direct multiplication of different magnitude scales is not a prior correction. Normalized density and numerical tail integration must be verified independently of the chosen point action.

For a real-clock replay, H_d consists of versions whose verifiable publication/receipt times are no later than d. Earlier origin time alone is insufficient. A latest modification timestamp cannot prove what a previous version said before d. Maintain stable event/version identifiers, issue and receipt times, reported versus revised magnitude/location, cancellations, association changes and field missingness. Filter availability before feature construction; exclude the current association and prevent coda-related updates from masquerading as prior knowledge. If this exclusion cannot be made using information available at d, report the ambiguity rather than use a final label to solve it.

The first defensible simplification is a background state frozen before the first operational trigger, reused at +1/+3/+5 while only the waveform/pick prefix changes. A separate update arm may accept new background messages before each deadline, retaining issuance latency and association rules. Retrospective first associated catalog P is not an operational detector time; a prefix at that clock supports only a retrospective experiment unless an online picker/transport replay is added. [GeoNet's official FDSN documentation](https://www.geonet.org.nz/data/access/FDSN) distinguishes archive data from incomplete near-real-time data with delays; it does not establish historical catalog-version availability at our deadlines.

Measure end-to-end state-update, query marginalization and posterior/action computation latency on the deployment runtime. A preencoded catalog state may reduce query cost, but it must update only when messages arrive and carry its exact version/availability receipt. Precomputing features from the final complete catalog cannot satisfy an absolute issue deadline. Prior held-out events may be permissible context only through messages actually published before the current deadline under a frozen evaluator; their final labels remain sealed from fitting and model selection. This proposal does not authorize reading existing TEST data.

Our current selected CMT/event metadata are a target census and waveform feasibility sample, not a complete background catalog. Their sparse origin minute timestamps, selected magnitudes, missing coverage and latest reviewed fields cannot reconstruct small-event rates, completeness, publication latency or the large majority of preceding catalog history. Do not reuse these rows as if they were MAGNET inputs. A separate source-defined background population, magnitude-scale mapping, completeness/latency audit and version-preserving acquisition protocol are required. No actual background catalog or current event rows were opened for this proposal.
