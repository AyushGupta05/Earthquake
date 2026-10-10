# Chile TEAM-LM training clock: source-only audit and bounded control proposal

Status: source inspection and exact theoretical enumeration only, 2026-10-10. No checkpoint, waveform, catalog row, training metric, DEV/TEST result, or fitting job was read or run for this audit. Downloaded author files and inspected local implementation identities are pinned in `manifest.json`; exact enumeration is in `clock_coverage.json`.

## Recommendation

Test a **matched continuation with a different training-clock distribution** before proposing another output head. This is a targeted baseline control, not a new statistical principle or architecture. The current port already exposes `--training-cutoff discrete` for 1/3/5 seconds. The missing evidence is a correctly paired run against continued training with the source clock law.

Do not change pre-P magnitude labels to zero. Both author and port preserve the earthquake's magnitude under pre-P cropping. There is no demonstrated noise-labeling bug in these paths. The source clock allocates 68.931% of crop counts beyond five seconds; this is an objective-allocation mismatch worth testing, not proof that late observations harm early prediction.

## Primary source and author-versus-port semantics

Author source is pinned to [TEAM commit 8df20877](https://github.com/yetinam/TEAM/tree/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903), with the published [software DOI](https://doi.org/10.5880/GFZ.2.4.2021.003). The [TEAM-LM paper](https://arxiv.org/pdf/2101.02010) explicitly scopes the problem as characterization rather than event detection/noise separation (§2.1). Its clock starts five seconds before the first **network** P arrival; continuous Chile stations may still contain only noise. The paper uses random temporal blinding in training and evaluates at 0.5/1/2/4/8/16/25 seconds (§§2.2, 3.1). Chile labels are MA, a displacement-based scale, not interchangeable with Mw. Consequently this control cannot be compared directly with a single-station post-P 1/3/5-second benchmark.

Exact implementation evidence:

| Item | Author source | Current port |
|---|---|---|
| Station pretraining target | `train.py:226–241` repeats catalog magnitude across stations; `util.py:52–71` crops X and returns that y. | `train_team_lm.py:446–462` retains y, applies the source smoothing, and crops the input. |
| Event target | `util.py:239,271–281,374–386` takes catalog MA, then returns it regardless of cutoff. | `train_team_lm.py:669–675` retains the event magnitude regardless of cutoff. |
| Label smoothing | For MA>4, add Gaussian noise with standard deviation `0.05*(MA-4)`; no noise-class target. | `smooth_training_magnitudes`, lines 371–375, uses the same law. Evaluation targets are not smoothed. |
| Crop law | `chile_mag_noloc.json` sets −4 to 25 seconds; `train.py:245–247,321–323` adds the default five-second lead-in. `util.py:66,256` draws one scalar crop **per batch**. | `training_cutoffs`, lines 483–491, draws a crop **per event** with the same marginal distribution. This differs in within-batch correlation. |
| Preprocessing | `util.py:258` includes index `cutout` in its mean before zeroing indices `>=cutout`. | `team_lm.py:79–88` computes the mean only over retained indices. This existing correction stays fixed in both proposed arms. |
| Station availability | Optional author trigger gating removes unavailable stations, not labels (`util.py:263–266`); Chile config does not activate it. | `prepare_prefix` uses observed support and supplied availability; no new P-pick gate or label reassignment. |

Relevant author code: [util.py](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/util.py), [train.py](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/train.py), and [Chile magnitude configuration](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/magloc_configs/chile_mag_noloc.json).

For an event-conditioned task, a pre-arrival input can legitimately supervise the distribution of the eventual event magnitude. With no informative early signal, the best available distribution is an event-conditioned prior, potentially depending on legitimately available station/noise context. Source magnitude resampling and label smoothing modify the training target distribution; this is not automatically the natural deployment prior. The code is not learning an explicit event-versus-noise probability. A label MA=0 would remain a magnitude value, not a defined non-earthquake class. Introducing a detector or background mixture would require a separately justified detection target and representative non-event data.

The author mean includes one sample outside its declared retained crop; at the n=500 boundary that can include the first P sample. The corrected port does not. This is a separate preprocessing issue, not evidence for relabeling, and the proposed clock comparison must not reintroduce it.

## Optimizer source audit

The author configuration initializes Adam at 1e-4. Author `train.py:265,364–365` reduces LR by 0.3 after four stagnant pretraining validations or six stagnant event validations. Port `train_team_lm.py:399–419,645–647` starts event Adam at 1e-4 and uses PyTorch patience 3/5 to match the corresponding four/six bad-observation convention. Its calibration monitor averages proper NLL at 1/3/5 seconds; therefore changing clocks while allowing separate adaptive schedules would also change the LR path. Neither source specifies a fixed final LR. The realized value requires the original optimizer/history state; the selected epoch number alone cannot determine it. No such state was read here. The proposed common constant 9e-6 is on the source decay grid, but is a new, explicit shared fine-tuning setting.

## Exact clock coverage, not observed training statistics

Let n be the retained sample count and let the first network P sample be index 500. The source configuration gives

`n ~ UniformInteger{100,...,2999}`, with 2,900 equally likely values,

and nominal cutoff `t=n/100-5` seconds. Retained indices satisfy `0 <= j < n`. The port passes `(n+0.5)/100-5` internally so floating-point flooring reliably recovers n; this does not supply another sample. Requested 1/3/5-second deadlines retain n=600/800/1000 samples.

The following rows partition all possible draws:

| Crop condition | Counts | Probability |
|---|---:|---:|
| n≤500: no P-or-later sample retained by the corrected port | 401 | 13.827586% |
| 0<t≤1 seconds | 100 | 3.448276% |
| 1<t≤3 seconds | 200 | 6.896552% |
| 3<t≤5 seconds | 200 | 6.896552% |
| t>5 seconds | 1,999 | 68.931034% |

Strictly negative nominal times account for 400/2900=13.793103%; the extra boundary count above is t=0. Nominal 0≤t≤5 accounts for 501/2900=17.275862%; t≤5 including pre-P accounts for 901/2900=31.068966%. The nominal median is 10.495 seconds. Each exact deployment deadline occurs with probability 1/2900; their union is 3/2900=0.103448%. Half-open ±0.5-second neighborhoods around the three deadlines contain 300/2900=10.344828% of crop counts.

These are source-defined probabilities, independently enumerated using integer arithmetic. They are not measured training exposure. Nearby cutoffs can teach transferable features, and the shared model can benefit from late examples; the tiny exact-deadline probability alone is not a starvation argument. Magnitude oversampling changes event exposure, but the clock is sampled independently of the label. Current calibration/model selection already uses 1/3/5 seconds, so the baseline is not wholly indifferent to the requested clocks.

## Prospective matched control, no execution authorized by this memo

Proposed bounded grid: two arms × two continuation seeds, six event-training epochs per run, no new station pretraining. This is a recommendation to freeze and review before any data or optimizer work, not an implemented protocol.

1. **Shared starting point:** the same parent-verified, TRAIN-calibration-selected epoch-97 `model.pth`, after completion of all 25 pretraining and 100 event epochs. Pin its SHA, original run/config/split/source hashes, and full histories. Do not choose another checkpoint after seeing results. The port's selected artifact contains no optimizer state for its selected epoch (`train_team_lm.py:724`); initialize identical fresh Adam states in both arms and call this fine-tuning, not an exact optimizer resume.
2. **Arm A, source-clock marginal control:** independently sample each event's n uniformly from 100…2999. Retain the current port's per-event sampling, not a new author batch-shared variant.
3. **Arm B, deadline-balanced control:** independently sample 1, 3, or 5 seconds with probability 1/3 each. “Balanced” means the sampling law; record realized counts without modifying them after outcomes. Use one forward/update per batch in each arm, not three B forwards for one A forward.
4. **Identical training exposure:** use all and only the original TRAIN-fitting events, with unchanged magnitude resampling, station selection, batch size, remainder handling, loss floor, magnitude smoothing, gradient clipping, architecture, and precision/determinism flags. Use continuation seeds 20261011 and 20261012 for both arms. Record hashes of event-occurrence order, station selections, and augmentation random draws per epoch. No additional target reweighting, detector, head, data augmentation, or station gating.
5. **Isolate random streams:** clock RNG must not consume station-blinding, smoothing, data-order, or model/dropout RNG. Both arms must receive identical base station-blinding uniforms/rank scores and label-noise normals for each paired event occurrence. The final blinding mask may differ if the cutoff changes causally observed station activity; impose the same transformation of the same base randomness, never force an unavailable station into an arm. Current author configuration has zero attention/hidden dropout; still pin any model RNG path. An identical-clock replay must match before the different-clock comparison.
6. **Fixed optimization budget:** use Adam at constant 9e-6, the same original port optimizer defaults and clip norm 1, six epochs, last completed epoch as the sole comparison checkpoint. No arm-specific plateau schedule or best-epoch selection. The value 9e-6 is 1e-4 multiplied by two source decay factors of 0.3. This lower-LR reset is an explicit common fine-tuning choice, not a reproduction of the baseline's adaptive trajectory or an assertion about its actual epoch-97 LR. Pin the exact baseline batch size from its verified config before launch rather than assume the author's batch 64 was used in the port.
7. **Evaluation:** after all six epochs and final-checkpoint hashing, evaluate the original TRAIN-calibration and existing DEV populations at 1/3/5 seconds with unchanged deterministic station/availability rules and unsmoothed labels. Save every prediction and event identity; compute paired bulk MAE, MedAE, mean bias, mixture NLL, and each high-MA event's errors. Report the unchanged starting checkpoint as context, but the causal comparison is B versus equally trained A. No inter-epoch calibration or DEV result changes an optimizer, checkpoint, epoch budget, or arm. TEST stays sealed. This document proposes those final evaluations; it performs no real-data evaluation or launch. DEV has already been used in the project and is not a newly untouched test set; broader generalization still needs a separately frozen external/test protocol.

The objectives are the same loss under two clock distributions:

`L_A(theta)=E_event,augmentation E_{n uniform 100:2999}[-log(p_theta(M_tilde|X_<n)+epsilon)]`,

`L_B(theta)=E_event,augmentation (1/3) sum_{t in {1,3,5}}[-log(p_theta(M_tilde|X_<100(t+5))+epsilon)]`.

This is task-distribution alignment. It adds no information to a prefix, proves no new proper-score theorem, and makes no rupture-identifiability claim. The existing density-floor negative result is unchanged; epsilon is not removed in either arm.

## Falsification and scope

The concrete hypothesis is that allocating updates to the requested deadlines improves their finite-budget fit. Use the equal-deadline average of event-level mean-prediction MAE as the primary point metric. The clock-allocation hypothesis passes this bounded control only if B improves this metric over A in both seeds on DEV, while no deadline in either seed worsens DEV MAE or MedAE by more than 0.002. Report the same tests on TRAIN-calibration as supporting evidence, without selecting checkpoints from them. If B does not meet these fixed criteria, reject the practical benefit claim for this continuation, even if it improves over the uncontinued checkpoint. A passing aggregate control supports a better deployment baseline, not a high-magnitude claim. Report all three deadlines, both seeds, MAE/MedAE/NLL and individual tail events; no winning-clock or winning-seed selection. The 0.002 tolerance is an operational margin, not a statistical guarantee. Also report paired event-bootstrap 95% intervals for bulk mean differences, with fixed bootstrap seed 20261013 and 2,000 draws, separately by continuation seed; retain paired events across deadlines. These intervals describe this event cohort, not independent training initializations or earthquake sequences. Label a passing sign/margin comparison inconclusive if the bulk intervals remain compatible with no benefit. Report NLL as a probability-quality guardrail: worsening proper NLL is a tradeoff and precludes claiming universal distributional improvement, even if point errors pass. Do not average seeds to conceal a failed paired seed.

Parent-reported completed-run context is 17.8 hours for the original 25+100 budget, 20 distinct high-MA TRAIN-fitting events and only two TRAIN-calibration high-MA events. This audit did not reread those artifacts. Two held-out tail events cannot establish large-earthquake generalization or a foundational-method claim. Tail improvements on the 20 fitting events would be training diagnostics only. Even a clean positive B-vs-A result would justify a stronger deadline-matched baseline; it would not establish superiority to the paper, another magnitude scale, or an external cohort. Potential degradation outside 1/3/5 seconds remains unmeasured unless a separately frozen late-clock audit is approved.

The closest prior method is the author's own random temporal blinding; the exact proposed discrete sampler already exists in our port. Thus no further novelty search is needed to classify this as a known-method baseline control. A negative paired result is useful: it rejects short-budget clock adaptation at the chosen LR, but does not rule out full from-scratch deadline training, other fixed budgets, or the clock mechanism generally. Six epochs span many repeated event updates and can reveal a useful local adaptation; they are not a convergence study. A clear positive result is more informative than a negative one about whether this clock control strengthens the existing deployed model.

Cost remains to be bounded from the parent's verified event-epoch timing and available ledger, without reading outcomes: four runs add 24 event epochs and four final calibration-plus-DEV evaluations, with no pretraining. The 17.8-hour total alone cannot reliably isolate event-epoch cost. Recommend a 5,400-second hard wall-time cap per run (six GPU-hours maximum across the four planned runs), subject to parent credit/runtime verification, and no automatic extension; a timed-out arm is incomplete, not a negative scientific result. No paid execution was started by this audit.
