# Event-held-out contextual threshold score: bounded pilot

Decision: implement and falsify on the existing instrument-conditioned residual head. The concrete EEW problem is uneven early magnitude evidence across instrument, waveform shape and amplitude regimes: a single global tail threshold cannot distinguish a routinely plausible magnitude from one surprising under a particular early prefix. This is a hypothesis about finite-capacity fitting and conditional errors, not a claim that a new statistical principle is needed.

For TRAIN event fold f, fit a CE-only reference R_{−f}(z|x_t) on all other events. x contains exactly the existing 51 prefix descriptors and 34 static instrument/site fields. It excludes the original all-TRAIN CNN's 66 logits and 128 embedding coordinates, all labels in inference, distance/depth/catalog variables, all future descriptors, and all 12 native-amplitude slots. Reference feature normalization is fitted with population inclusion weights on the retained folds only. The upstream count scaling is the existing target-free all-TRAIN covariate normalization, so this is label-isolated cross-fitting rather than an assertion of a wholly inductive unseen-covariate preprocessing pipeline.

At interior cut z_k=(k+1)0.1, define

    u_ik = min(25, 1/(0.01 + R_ik(1−R_ik)))
    w_ik = u_ik / mean_k(u_ik)
    L_i = 0.1 Σ_k w_ik [F_theta,ik − 1(Y_i≤k)]² + 0.075 CE(p_theta,i,Y_i).

Here Y is the existing discretized magnitude-bin label. Weights are frozen before student fitting. Every vector has arithmetic mean one; this removes a hidden per-record scalar emphasis, although it does not equalize gradient norms. **Inverse variance emphasizes confident lower/upper CDF regions, not maximal-entropy thresholds.** An unexpected outcome in those regions then incurs greater loss. It is symmetric in lower/upper CDF tails and is not specifically a high-magnitude-only loss. Cap25 limits the raw threshold ratio to 6.5; many empty high thresholds may saturate and weaken context variation.

For fixed x and exogenous frozen reference, writing the true CDF Q,

    E[L(F,Y)−L(Q,Y)|x,R] = 0.1 Σ_k w_k(x)(F_k−Q_k)²
                           +0.075 KL(q||p).

Thus the ideal target remains Q. This does not prove calibration of a learned finite-bin, bounded-head estimate, point-error improvement, or fixed MAE/MedAE. It changes the metric used to project onto a restricted model family. It resembles diagonal residual preconditioning, but generally changes the optimizer's finite-model optimum; it is not equivalent to an optimizer-only preconditioner. We must not recompute w from the student, even with detached gradients: the dynamic vector field would not minimize this fixed proper objective.

## Near prior art and exact boundaries

- [Gneiting and Ranjan (2011)](https://www.tandfonline.com/doi/abs/10.1198/jbes.2010.08110) provides threshold-weighted CRPS. The score above is a direct conditional instance of that established construction. Its positivity/propriety is not our contribution.
- [Allen (2024), Weighted scoringRules](https://www.jstatsoft.org/article/view/v110i08) develops software and distinctions among threshold/outcome weighting. Fixed reference-shaped weights remain in that established class; weighting the realized magnitude's ordinary NLL would instead tilt the conditional density.
- [Bolin and Wallin, local scale invariance](https://arxiv.org/abs/1912.05642) studies scale effects and scaled proper scores. Our per-record threshold normalization is not their local scale-invariance construction and should not be called a scale-invariant score.
- [Wessel et al., weighted-score wind training](https://doi.org/10.1175/MWR-D-24-0151.1) directly precedes using twCRPS in training for extreme-event performance and its central/tail trade-off. Merely training a weighted score for rare outcomes is not distinct.
- [Barczy (2020), Proposition1.3/Eq1.5](https://arxiv.org/html/1912.07572v2) supplies the properized Anderson–Darling-inspired competitor: at each threshold I sqrt((1−F)/F)+(1−I)sqrt(F/(1−F)). This uses current F in the properly derived full score, unlike arbitrary frozen or detached inverse variance. It is included alongside ranked BCE so the reference method cannot benefit merely from omitting strong known tail-sensitive proper scores.

The narrow method under test is **event-excluded, instrument/prefix-context reference metrics for early magnitude distributions**, with unchanged deployed head and no reference inference cost. I have not established an exact earlier EEW implementation or a priority claim; the present contribution could only be an empirically effective, explicitly delimited supervision modification. Cross-fitting plus known weighted CRPS alone is not sufficient for a foundational claim.

## Close mathematical equivalence to ranked log loss

For one threshold with true Bernoulli probability q, the expected binary-log-score excess is KL(Ber(q)||Ber(p)). Around p=q it is (p−q)²/[2q(1−q)] + O((p−q)³). Therefore a frozen accurate reference R≈q gives a **regularized, capped, locally quadratic approximation to the ranked-log geometry**, before the per-record normalizer. This is an important near-equivalence, not an unrelated comparator. The normalizer also rescales that local geometry as a function of x; it changes finite-model fitting and the relative importance of the fixed .075CE term despite holding threshold-mean weight at one. If the new arm merely matches rankedBCE, the teacher/fold machinery has not shown practical value. Any narrower claim would be that a stable, exogenously estimated, capped local metric works better under early-prefix/instrument heterogeneity than the direct proper binary log score; the matched control can refute that claim.

## Fixed pilot and controls

Student: exact existing 291-input ResidualDistribution; 34 static fields active, 12 native slots zero, original feature extraction/cache alignment, weighted TRAIN normalization, inverse-inclusion recording weights, 197676 rows (`max_per_event=4`, all rare rows), 15 epochs, batch2048, AdamW5e−4, clipping5, seeds20261009/20261010, separate1/3/5s fits. No validation selection. Deterministic CUDA/cuBLAS flags and realized initialization/shuffle hashes are recorded.

Five target-independent SHA256 event folds. Each reference85→128→64→66, SiLU/dropout.1, CE-only, 15epochs, AdamW5e−4; reference seed20261011+fold, fixed across student controls/seeds, independently refit per horizon. Fold-only weighted normalizers are checkpointed. No validation labels or features enter reference fitting.

Prespecified controls, same student parameters/init/order/budget:

1. OrdinaryCRPS+.075CE.
2. Context weights above+.075CE.
3. Whole weight-vector permutation **inside each held-out event fold**+.075CE. Its teacher excludes all donor and receiving fold labels. Same-event donors/fixed points are permitted and logged, not label-filtered. Different inclusion weights can alter its population-weighted threshold average; that change is logged.
4. Population-weighted TRAIN average of the contextual vectors+.075CE. This is a fixed global threshold baseline estimated on TRAIN, not a per-record event-excluded reference: averaging across folds indirectly uses each fold's labels through other models.
5. Ranked binary log score+.075CE, same population/protocol as this pilot.
6. Known properizedAD+.075CE, double log-cumulative-sum implementation. No probability or exponent clipping changes its formula. Abort explicitly if an exponent exceeds60 or gradient is nonfinite; report failure, do not silently relabel a clipped score as properAD. This conservative fixed computational bound does not alter successful runs' objective. Preclip gradient diagnostics reveal whether clipping dominates.

Teacher diagnostics: OOF population-weighted/unweighted NLL, probability/CDF/weight quantiles, cap fraction, normalization error, hash identities, permutation fixed/same-event fractions. The exact aligned OOF probability/CDF, folds, donor rows, record/event/trace IDs, targets, inclusion weights, per-fold models and normalizers are saved before students. Reference CDFs can later support 1s-weight→3s-student or3s→5s without refitting, but those arms are not included now.

## Decisive interpretation

Context must outperform ordinary and ranked-log/AD baselines and both context-removal controls consistently across seeds; report every arm even if negative. Use mean and median decisions, bulkMAE/MedAE, high-magnitude errors and event-macro errors, CVaR95, false high alerts, CRPS and NLL; check teacher failures and clipping. A gain shared by shuffle/average is evidence for a global score-shaping effect, not conditional early evidence. A gain confined to a single horizon/seed or13 repeated exploratory high-magnitude validation events needs more independent support. Compare against the strong instrument Huber baseline too; winning a proper-score subgrid does not beat the existing best model.

Potential failures: overconfident misspecified teachers amplify wrong regimes; extreme thresholds cap out and become uniform; poor fold-tail coverage; teacher capacity drives arbitrary weight shape; average/shuffle changes inclusion-weighted emphasis; static features encode station/domain priors; properAD gradients dominate clipping; bounded student logits limit repair. Current INSTANCE release processing/manual P issues remain. External frozen event cohorts and strict-prefix causality audits are required before superiority claims.

No live GPU run was launched by this implementation subtask. Parent owns scheduling and all resource decisions.
