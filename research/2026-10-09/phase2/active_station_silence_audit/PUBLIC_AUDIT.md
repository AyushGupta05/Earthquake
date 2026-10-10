# Audit of active stations that have not triggered

10 October 2026, 23:16 UTC. Primary literature, existing research reports and source inspection only. No real records, waveforms, picks, station inventories, checkpoints or held outcomes were read. No author code was executed. No training implementation, fit, AWS action or Git change was made.

**Recommendation: zero fits for this hypothesis now.** Verified operational silence can constrain a source posterior, but that mechanism has substantial prior art. Our Chile TEAM-LM baseline already receives continuous noise-only station prefixes. Historical health, picker state and packet receipt times needed for a distinct operational observation are not verified by the inspected project provenance. This is an availability and distinctness gate failure, not a proof that silence is useless.

## Relation to current work

The inspected [method status](../../earthquake_method_status.md) reports a completed useful static instrument/site baseline improvement, many retained negative distribution pilots, and an ongoing matched Chile training-clock control. Novelty or independent published-benchmark superiority is not established. This audit does not change that control's [frozen protocol](../../phase3/chile_clock_control/protocol.json).

The completed [censored-innovation pilot](../../earthquake_censored_results.md) modeled growth of the already observed local peak from 1 to 3 to 5 seconds, with tied, free-hurdle, uncensored and discriminative controls. It improved a stale 1-second forecast but did not surpass full-prefix inference consistently. Network non-arrivals are a different observation; that negative result alone does not reject them. It also does not justify rebranding the same scalar censoring mechanism.

## What the primary sources establish

| Source and inspected scope | Relevant mechanism and limit |
|---|---|
| [Cua and Heaton, original Virtual Seismologist chapter](https://www.its.caltech.edu/~heatont/papers/VSmethod_cua_heaton%20(2).pdf), §2.3, pp. 6–7 | Neighboring operating stations without a subsequent P detection constrain location as time advances after the first trigger. Station health is among the proposed prior information. The geometric constraint supplements amplitude-based joint magnitude/location inference; this is clear earlier negative-station evidence. It is not proof every later VS implementation retained every proposed prior. |
| [Satriano's author-hosted 2006 thesis](https://www.ipgp.fr/~satriano/Satriano-2006_PhD_Thesis-slim.pdf), Fig. 2.1, p. 22; [RTLoc 2008 publication identity](https://doi.org/10.1785/0120060159) | The author thesis explicitly separates known operational and nonoperational stations. Conditional equal-differential-time surfaces from operational stations that have not triggered shrink the possible source region. This verifies earlier health-conditioned silence for location. The 2008 publisher full text was inaccessible here; no additional detailed paper result is inferred from that failure. |
| [Wu, Yamada, Tamaribuchi and Beck 2015](https://academic.oup.com/gji/article/200/2/791/610068), §4.2–4.3, primary publisher search excerpt; [author repository](https://authors.library.caltech.edu/records/0cdjs-00z18) | In joint multi-event Bayesian estimation, a nontriggered station penalizes candidates whose predicted P arrival is earlier than the current time. Candidates predicting a future arrival get factor one. A likelihood floor of 0.004 protects against a malfunctioning station. This clipped Gaussian rule should not be silently relabeled a normalized survival likelihood. |
| [Prior-informed IPF / IPFx 2026](https://link.springer.com/article/10.1186/s40623-026-02488-7), §3 | IPFx derives trigger information from server-side waveforms. Its likelihood includes a noise-level amplitude factor for stations without an observed P wave, with magnitude marginalized; absence is already part of joint inference. This establishes additional negative-amplitude prior art. It does not establish a calibrated packet-delay/health survival model. |
| [TEAM-LM 2021](https://arxiv.org/pdf/2101.02010), §2.1–2.2 | Station waveforms share a network clock and include pre-arrival noise. Italy/Japan apply trigger-based selection; Chile uses continuously available station data, so the trigger gate is unnecessary there. The study explicitly separates characterization from event detection. Its magnitude distribution is already an all-observed-station alternative to an explicit silence likelihood. |
| [SINE 2025](https://www.sciencedirect.com/science/article/abs/pii/S0098300425001244), publisher abstract and section previews | The model jointly estimates P arrival, location and magnitude from continuous waveforms using graph features, Bi-LSTM and attention. The accessible preview does not verify a health-conditioned nontrigger survival likelihood or packet receipt model. Neither its absence nor matched 1/3/5-second EEW superiority can be inferred without a full protocol/source audit. |
| [Allen et al. 2009 ElarmS](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2008GL036766), Fig. 1 and §5 | The operational study separates sample timestamp, first receipt at the processing center and trigger incorporation into output. Packet filling and transfers contribute latency. It therefore supports distinguishing physical non-arrival from missing center receipt; its historical delay values are not assumed to describe today's networks. |

The original VS, RTLoc and Bayesian/IPFx examples are sufficient to reject novelty for the generic idea of multiplying a magnitude/source distribution by negative station evidence. A more reliable implementation could still be useful; usefulness would require matched empirical evidence.

## What is actually observed at the deadline

The following equations are our audit derivation, not a transcription of an author's algorithm. Let the common center-processing deadline be `d`, the source/nuisance state be `theta`, and a station's latest completely received and picker-processed sample time be its watermark `w_j(d)`. A station is eligible as verified silent only when its channel is healthy, the picker is enabled with known configuration/history, samples are continuous through that watermark, and no associated causal trigger has occurred through it. A healthy station with delayed packets is not silently observed through `d`.

For a hypothetical station-local P arrival `A_j`, nonnegative detection delay `D_j`, packet/parameter delay `L_j`, and possible missed detection, center nonreceipt can mean:

`A_j + D_j + L_j > d`, or a miss, or an unavailable station.

It does not establish `A_j > d`. Physical travel-time non-arrival mainly constrains geometry. Magnitude information requires magnitude-dependent detectability, attenuation/noise and integration over the unresolved source location; one cannot insert the true catalog geometry at inference.

For verified received samples, a suitable conditional model is a picker survival probability `S_j(w | theta, health, noise, picker history)`. For center receipt, use its receipt-time counterpart. If availability has independent probability `a`, a simple illustrative mixture is

`P(no receipt by d | theta) = (1-a) + a * S_receipt(d | theta)`.

Independence of availability and source is an explicit assumption, not universal. Unknown state must otherwise be integrated jointly. False triggers and association errors also require a model. Multiplying station factors requires justified conditional independence; shared noise, common telemetry and coincident events can break it.

For repeated silence at 1, 3 and 5 seconds, update with conditional increments such as `S(3)/S(1)`, then `S(5)/S(3)`, when these are defined. Multiplying all three cumulative survival probabilities double-counts nested evidence. If the earlier probability is zero, that branch requires explicit model handling rather than division.

## Invented finite counterexample

The probabilities below are deliberately invented and checked by exact rational arithmetic in [counterexample.json](counterexample.json). They are not observed detection rates, calibrated models or a performance result. Equal prior mass is assigned to a large and small magnitude hypothesis. For a known healthy, observed station, survival probabilities are:

| Common deadline | Large hypothesis: no trigger | Small hypothesis: no trigger | Posterior probability of large after silence |
|---|---:|---:|---:|
| 1 second | 4/5 | 19/20 | 16/35 ≈ 0.4571 |
| 3 seconds | 1/10 | 4/5 | 1/9 ≈ 0.1111 |
| 5 seconds | 1/20 | 7/10 | 1/15 ≈ 0.0667 |

Silence can therefore carry magnitude information after an arrival should have been detectable. At 3 seconds, a known outage instead leaves the large-event probability at 1/2. If the only known availability probability is 1/10, the correct no-receipt likelihoods are 91/100 and 98/100, yielding 91/189 ≈ 0.4815. Treating that unknown station as healthy would spuriously collapse the tail to 1/9.

A separate deterministic clock example sets local P arrival at 1.0 seconds, picker delay at 0.1 seconds, and transmission delay at 3.0 seconds, all relative to the same first received network trigger. The trigger is available at the center only at 4.1 seconds. Nonreceipt at 3 seconds is compatible with the large event. This example models trigger-message delay; waveform receipt needs its own watermark and can follow a different transport path.

Exact incremental updates recover the 3/5-second posteriors. Incorrectly multiplying the cumulative factors at every deadline produces 2/21 at 3 seconds and 1/134 at 5 seconds: excessive rejection caused solely by reuse of the same silence.

## Availability in our current project

This is an audit of available documentation and source, not an exhaustive search of provider operations logs. No inspected report certifies historical center receipt, picker health/configuration and event-association state at every requested deadline. Such logs may exist elsewhere; they have not been established here.

| Resource | Established by inspected provenance | Missing for observed operational silence |
|---|---|---|
| Chile TEAM-LM | Continuous station prefixes, supplied station mask, source network-first-P sample clock. The pinned author config does not enable `trigger_based`; our port has no inferred P-pick gate. | Historical packet watermarks and health/picker/association histories. Nonzero prefix support is an archive-input rule, not an operational health certificate. |
| INSTANCE work | Controlled individual-record post-P characterization, released full-record preprocessing caveats. | A complete online network denominator and active nontriggered stations, plus receipt/picker histories. Missing records/picks cannot supply it. |
| GeoNet expansion | Retrospective preferred-origin P picks, public archive/StationXML access and a completed metadata feasibility census. | Receipt-by-deadline and picker/health state. The [FDSN service](https://www.geonet.org.nz/data/access/FDSN) describes a seven-day archive lag and near-real-time webservice delays expected below one minute for high-frequency channels and five minutes for low-frequency channels. Those are webservice delivery descriptions, not per-packet native SeisComP EEW telemetry logs or proof native telemetry has those delays. |
| Alaska release | Header/segment and cohort audits; archived station/gain tables. | Online receipt, picker health and a verified common operational clock. Headers/padding and catalog absence do not establish silence. |
| TEAM Japan | Event-triggered KiK-net recording, as described in the primary paper. | Noise-only nontriggered stations are not recovered merely by taking the complement of an event's released records. |

Exact local evidence pointers are pinned in [manifest.json](manifest.json). The Chile author source is [commit 8df20877f3a6ef47d3af4d1484ecdb0cdf37e903](https://github.com/yetinam/TEAM/tree/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903): `util.py:263–266` masks nontriggered data only when enabled; the README default is false and `magloc_configs/chile_mag_noloc.json` omits the flag. Our port's `prepare_prefix` keeps nonzero observed noise as an available station and receives coordinates.

If a binary silence bit is a deterministic causal function of the same supplied waveform prefix, picker configuration and initial state, then `I(M; silence | those inputs) = 0`. A learned finite model can benefit from that feature or an inductive bias, but it is not newly observed information. If the picker uses longer history or external health/receipt state, those are additional inputs and must be supplied equally to all controls. This distinction does not claim TEAM has optimally learned every useful function of its inputs.

## Falsification before any future fits

1. **Availability gate:** establish actual historical health, picker/association configuration/history and packet/parameter receipt provenance. Freeze what is genuinely observable at each station's watermark. If only archive sample times exist, label the exercise an oracle/sample-time replay, not actual receipt-time EEW. Do not equate a missing catalog pick with an observed online nontrigger.
2. **One common clock:** choose first causal network-trigger receipt for an operational experiment, then 1/3/5 seconds from that single timestamp. For an archive characterization control, explicitly use the common network-first-P sample clock for every arm. Never mix those clock definitions or give each station its own post-P budget.
3. **Equal observable inputs:** compare an all-received-station waveform/coordinate/status baseline, an equally resourced discriminative silence/status feature control, and an explicit joint source/detection-delay survival formulation. Give every arm identical received noise-only stations, timestamps/watermarks, health state and picker history. A triggered-only comparator alone confounds more observations with a better mechanism. Match training events, capacity/budget and output distribution/readout; keep classical VS/RTLoc/IPFx lineage explicit.
4. **Causal isolation:** freeze an actual causal picker with state carried from pre-event noise. Source-hypothesis travel times may enter the likelihood; catalog location, future nearest-station selection, eventual picks and true arrival times may not enter features or masks. Retain unknown/outage/delay states separately. Use nested survival increments once, and report event-class/association ambiguity.
5. **Adverse controls:** on a prospectively frozen common event cohort, test controlled packet delays and outages with the same affected observations withheld from every arm. Report the source of simulated availability/delay laws. A method that suppresses large magnitudes merely because unknown state is interpreted as silence fails. If a gain disappears against the all-station or equal-input status-feature control, reject a distinct-information/mechanism claim.
6. **Independent endpoint:** before outcomes, fix native magnitude definitions, high-magnitude event thresholds and event-balanced reporting at all three times. Require high-tail improvement with prespecified bulk MAE/MedAE and worst-error guards, proper distribution scores and event-level uncertainty. No best-seed/deadline selection, recurrent-DEV superiority claim, or published comparison with unmatched clock/selection/magnitude scale.

These are falsification conditions, not a new frozen training protocol. Current documented inputs fail the operational-availability gate; existing all-station inputs and strong prior art fail a generic novelty claim. Preserve this negative source audit and continue the already authorized, separately controlled work. **No training run is earned by this audit.**
