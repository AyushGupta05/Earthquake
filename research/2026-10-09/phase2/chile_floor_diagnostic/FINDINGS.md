# Chile density-floor diagnostic: negative closeout

The frozen high-magnitude gate failed: **0 of 20 distinct TRAIN-fit events with
MA ≥ 5.5 qualified**, versus the required four. Stop the proposed floor-mechanism
training pilot. No threshold, magnitude cutoff, checkpoint, or population is
changed after seeing this result. No head or optimizer experiment is justified
by this diagnostic.

## Scope and evidence

This is the completed corrected v2 diagnostic, using the already selected epoch
97 checkpoint after 25 station and 100 event epochs. It evaluates 1,371 distinct
fit events: all 20 with MA ≥ 5.5, all 327 in [4, 5.5), and a fixed hash sample of
1,024 below 4. The 20 tail labels span MA 5.551–8.054. These are fitting examples,
not a generalization benchmark. The sampled bulk is not an unweighted estimate
of the entire TRAIN population.

The clock is **network-first P**, with the source model's five seconds of pre-P
input. It is not interchangeable with a single-station post-P benchmark. The
reported active station counts (11–21 for the tail) include continuous stations
with available pre-arrival noise; they do not count stations whose P waves have
already arrived. The source explicitly supplies no inferred P-pick gating.

I verified all four output hashes against `real_v2/COMPLETE.json` and inspected
only these authorized completed diagnostic outputs and the parent's replay.
The parent independently replayed Gaussian log densities, native point means,
attenuation, analytic output gradients, and the frozen event gate. This closeout
adds descriptive statistics from the same saved arrays, not a new forward pass.
The producer reports zero optimizer steps, zero calibration/DEV/TEST forwards,
and zero consultation of their metrics. Runtime was 199.734 seconds according
to the parent, and completion was verified. The stopped earlier attempt remains
preserved and is excluded; its only output was STARTED.json.

## What the floor does at this checkpoint

For mixture density p at the observed label and ε = 10⁻⁶, the output-gradient
multiplier is A = p/(p+ε): ∇[-log(p+ε)] = A ∇[-log p]. The predeclared gate requires
A < 0.1 together with mean underestimation > 0.5 at at least two deadlines for
at least four distinct MA ≥ 5.5 events.

| Network deadline | Tail mean-action MAE | Tail mean-action MedAE | Tail events underestimated > 0.5 | Minimum A | Maximum relative gradient reduction |
|---|---:|---:|---:|---:|---:|
| 1 s | 0.98904 | 0.45702 | 8/20 | 0.96309998 | 3.6900% |
| 3 s | 0.13445 | 0.04800 | 1/20 | 0.99959670 | 0.04033% |
| 5 s | 0.04228 | 0.03685 | 0/20 | 0.99999944 | 0.0000558% |

Minimum tail density relative to ε is approximately 26.10, 2,478.57, and
1,792,950.34 at the three deadlines. Thus these tail cases are far from the
predeclared strong-suppression regime. Median tail attenuation is even closer
to one. Replacing the floor with a log-domain implementation cannot be credited
with solving these current tail errors on this evidence.

Posterior-median action does not remove the observed early errors: its tail MAE
is 1.02221 / 0.13430 / 0.04207 at 1/3/5 s. This is a descriptive comparison only;
no action was selected to obtain a win. The small 5-second errors are on training
examples and are not evidence of external performance or state of the art.

## Responsibility concentration is a separate observation

Component responsibility is r_j = α_j f_j(y)/p(y), conditional on the known true
label. Concentration of r is different from the event-wide multiplier A. Using
an explicitly descriptive threshold, maximum responsibility is at least 0.99
for 17/20, 19/20, and 20/20 tail cases. Median responsibility entropy is 0.000180,
0.0000134, and 0.0000115 nats; median effective component count exp(H) is very
close to one. The learned mixture weights are also concentrated: median maximum
weight is 0.999665 / 0.999841 / 0.999807. Zero-based component 4 dominates target
responsibility for 19/20, 20/20, and 20/20 tail events. Component numbers have no
inherent physical meaning and can be permuted.

This establishes concentration in these fitting examples, not harmful mixture
collapse. A specialized component can correctly explain an observation; at 5 s
this concentration coexists with small fitting error. Conversely, the largest
1-second underestimation is not a nearly single-responsibility case:
`2007_10_25_08_35_16_680000` has MA 5.87, mean 1.88986, underestimation 3.98014,
A = 0.99968149, and maximum responsibility only 0.57091. Its dominant component
has mean 2.94839, scale 1.08602, and mixture weight 0.18187. By 3 s its mean is
6.02727. Another event, `2010_10_22_19_31_34_960000`, has 1-second underestimation
3.75832 with A = 0.99980043 and maximum responsibility 0.86879; it remains
underestimated by 1.31813 at 3 s but by only 0.09573 at 5 s. Broad components can
assign a non-negligible density at the true label while the posterior mean
remains low. This is not evidence that forcing higher responsibility entropy
would improve error.

## A non-tail outlier does not rescue the gate

Exactly one selected event has A < 0.1 at any deadline, and it does so at all
three: `2010_03_25_18_39_13_520000`, source row 39545, MA 4.399. Its A values are
approximately 3.46×10⁻⁹, 1.54×10⁻²⁶, and 6.84×10⁻⁵¹; mean underestimation is
2.73784 / 2.67637 / 2.60893. This is an actual isolated strongly suppressed
fitting case. Its label is below the frozen tail cutoff, so it is **not** a
qualifying event and does not license lowering the cutoff after the fact.
Neither its label nor waveform quality is established as erroneous by these
outputs. It is a candidate for a separately authorized data/clock audit, not a
reason to start a new loss experiment.

## What does not follow

- The result does not show that the floor never affected earlier training,
  station pretraining, different sampled cutoffs, other labels or checkpoints.
  Historical gradients were not recorded or reconstructed here.
- It does not show that the tail errors are irreducible or that the input lacks
  magnitude information. A low fitted density/point error is model-dependent;
  no optimal-observer or physical identifiability result was established.
- Analytic scores are derivatives with respect to output logits, means and
  scales. They omit neural Jacobians, ReLU activity, parameter cancellation,
  clipping, optimizer state and training history. Unsuppressed output gradients
  do not prove that all useful backbone updates are large.
- No result here establishes improved calibration, held-out error, a superior
  loss/head, or an advantage over published work. In particular, the hypothetical
  Huber score's different derivatives are not an empirical improvement.

## Bounded follow-up suggestions; not implementations or launch approvals

1. **Audit early noise/label semantics in source first.** The pinned
   `training_cutoffs(..., 'author')` includes approximately −4 to +25 s relative
   to first P. In the inspected station/event training path, labels remain event
   magnitudes (with optional Gaussian smoothing above MA 4); no explicit
   noise-only → MA 0 reassignment appears there. Check the original author's
   intended MA=0/noise contract and any upstream handling before treating this
   as a bug or changing labels. This saved diagnostic has no MA=0 observations
   and cannot resolve the semantics. An actual follow-up, if authorized, must
   use frozen TRAIN populations/cutoffs and report signal availability without
   using future picks as deployment inputs.
2. **Audit the isolated MA 4.399 failure's provenance and observed prefix.**
   Verify event/label/clock/response integrity against author metadata, then
   inspect only authorized prefixes. Preserve the event even if difficult;
   exclusions need an independently justified rule. This remains a data-quality
   question, not evidence that the high-tail floor gate passed.
3. **Check whether early mixture specialization generalizes before penalizing
   concentration.** A source-only next step is to map the fixed head's score,
   component routing and mean decision mathematically. Any new fit/held-out
   diagnostic or matched capacity ablation needs a separate frozen protocol.
   Do not turn the descriptive ≥0.99 cutoff into a learned gate or retune on
   these 20 fitting outcomes.

Numerical details and all 20 aligned tail cases are in `findings_metrics_v2.json`.
Original diagnostic sources, test files and source manifest remain unchanged.
