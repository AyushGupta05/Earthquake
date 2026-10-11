# GeoNet benchmark design options and limits

**A retrospective CMT-Mw raw-prefix benchmark is feasible to investigate; its final split and usable-event support are not established.** The next 346-event lower-M metadata screen is separate from full acquisition/training. It can quantify lower-band observed-P coverage and identify sequence/station audit prerequisites. It cannot prove bulk-error preservation, physical calibration or operational warning latency.

## Current calendar support, before sequence or waveform exclusions

The pinned frame contains 3,437 eligible unique CMT-Mw events, including 149 Mw≥5.5, 60 Mw≥6 and 15 Mw≥7. The proposed calendar partition has these upper supports:

| Candidate partition | All events | Mw≥5.5 | Mw≥6 | Mw≥7 |
|---|---:|---:|---:|---:|
| TRAIN 2003–2014 | 1,732 | 69 | 29 | 8 |
| DEV 2015–2017 | 566 | 31 | 12 | 2 |
| TEST 2018–2024 | 1,139 | 49 | 19 | 5 |

A proposed 30-day temporal guard on **both sides** of the 2015 and 2018 boundaries would quarantine 12/22/12 total events respectively. Remaining totals are 1,720/544/1,127; tail counts are 69/30/49 at Mw≥5.5 and unchanged 29/12/19 at Mw≥6. This is a calendar-only calculation. It does not establish independent earthquake sequences, stations or available prefixes. The metadata sample itself does not apply this guard or drop those events.

The future calendar test offers meaningful Mw≥5.5 support compared with the old reused 13-event tail, but only five potential Mw≥7 cases. Catalogue selection and network history differ across time. CMT-selected lower events support statements about this pinned CMT population, not the full natural NZ earthquake population. No ML→Mw conversion or pooling with Chile MA is justified.

## Compare designs before model outputs exist

| Option | What it can support | Main limit |
|---|---|---|
| Candidate calendar split, with sequence quarantine | Performance on later CMT events under changing network conditions | TEST has at most 49/19/5 tail events before missingness; calendar alone is not sequence isolation. |
| Sequence-grouped stratified split across 2003–2024 | Better allocation of scarce magnitude strata, potentially more ≥6 test events | Tests an exchangeable historical population, rather than future-calendar transfer; sequence metadata still needed. |
| Grouped out-of-fold forecasts across the tail frame | Mechanism diagnostics using more of the 149 tail events | Different fitted models and shared training samples; not a single sealed independent TEST result. Selection must be nested. |
| Reserve all ≥7 events as an extrapolation stress panel | Up to 15 largest-event case studies | Removing their sequences changes training support; this becomes a specific extrapolation task and cannot double as a natural-distribution benchmark. |
| Additional general catalogue / cross-region data | Potentially broader small-event bulk or more large events | New label/type, clock and sampling audits are needed. Existing Alaska-only or simulated large events cannot establish unchanged small-event bulk error. |

Prefer testing the candidate calendar support after metadata/sequence/availability audits. Do not shift dates or choose a competing design because of its prediction scores. A separate design freeze must precede fitting and scoring. No architecture grid is proposed.

## Leakage controls and clock contract

Keep every event and all its station records in one partition. A concrete sequence-screen candidate is a connected-component graph using preferred-origin time differences ≤30 days and great-circle distances ≤100 km, then quarantining every component crossing a calendar cut. Add the 30-day boundary guard and report sensitivity to a longer 90-day/150-km screen. These are transparent leakage heuristics, not verified physical sequence labels. Complete relevant-frame geometry and independently documented major sequences are needed; a graph on 495 sampled events can miss links through unqueried events. The current groups contain dates but no coordinates, so sequence-independent counts cannot be supplied now. Keep quarantine counts and reasons; do not move cross-boundary sequences into TRAIN to improve results.

Primary calendar evaluation may reuse training stations, with that fact reported. A distinct strict station-transfer panel can withhold a stable hash-selected 15% of physical station groups from every TRAIN/DEV encoder, normalization, calibration, metadata embedding and model-selection step. Freeze the station grouping/relocation and hash rules before any forecasts. Shared site/gain features can fingerprint a station; hiding its literal code is insufficient. Station-reuse and held-station results answer different questions. No held-station event counts are known from the CMT groups; a sparse secondary panel should not invalidate an otherwise useful clearly scoped engineering benchmark.

All models use the same T0: earliest accepted preferred-origin-associated NZ P annotation. At horizon t, expose only data strictly before T0+t for t=1/3/5; preserve pick provenance and strict deadline masks. A station's later P arrival does not grant it its own extra t-second window. Fixed station selection and whether inputs require an observed P annotation must be declared, matched across controls and based on the same available-prefix policy; report events with only one early station. Catalogue origin coordinates/distances may support split/reporting audits, but cannot enter these magnitude inputs. Do not use whole-record detrending, acausal resampling or a later suffix to prepare an earlier prefix.

This is an **annotation-conditioned retrospective task**. It does not reproduce causal online picking, association, packet receipt, telemetry delay or an end-to-end warning system. Those require a separate operational replay with missed detections retained.

## Engineering support versus stronger physical claims

Ordinary supervised controls require audited raw sample identities/timestamps, valid declared input channels, prefix-only preprocessing and explicit missingness. They do **not** need a claim of exact physical response calibration. Missing response metadata can be represented as missing for a counts-based baseline rather than excluding every event. Flatline/clipping screens are quality flags; a clean screen does not prove absence of clipping.

Full causal-response invariance or state-aware physical likelihood claims require the additional complete effective response, units/orientation, noise/state and transformation audit. Compare those methods against controls with the same information on an explicitly matched supported subpopulation, alongside their coverage. Do not impose those stronger gates on every engineering experiment or misattribute new metadata/context information to a new probability method.

The old 0..6.5/6.55 PMF support cannot be reused unchanged for Mw up to 8.0: its mean/median cannot reach the largest labels and creates a built-in error floor. Use adequate predeclared support/overflow or an unbounded density such as the matched Gaussian-mixture baseline. Match probabilistic support, training clocks, priors, input information and point decisions; do not compare a tuned median with an untuned mean. Mw and Chile MA remain distinct targets and score tables.

## Minimum outcome support and scoring objective

Planning floors for a later independent **available-prefix** test are at least **30 Mw≥5.5 events**, **15 Mw≥6 events**, and **200 total events** at every horizon after sequence quarantine, with failures/unknowns still reported against the original frame. These floors limit the most fragile pilots; they do not prove power. The calendar ceiling is 49/19/5, so ≥7 performance remains a five-case stress report, and attrition could erase the ≥6 floor. Use TRAIN-only out-of-fold residuals to predeclare a paired precision/power target before DEV/TEST predictions, then decide whether the surviving cohort can resolve the intended effect. No number of station records turns five earthquakes into many independent large events.

Report one magnitude distribution/decision per event at each horizon. Primary metrics are overall event MAE and MedAE, Mw≥5.5 event MAE, secondary ≥6 MAE, and CVaR95 of absolute error across all events. Include signed tail bias, P95/max absolute error and individual ≥7 cases, plus proper CRPS/NLL and calibration. Estimate paired uncertainty by sequence/event blocks, never by independent trace bootstrap. Account for all three horizons and the fixed model comparisons. Weighted summaries for the stratified feasibility sample target its CMT frame only under its sampling assumptions; waveform missingness is not automatically missing at random. Conditional available-case errors must accompany frozen-denominator coverage, not zero-error imputation for failures.

A later method claim requires tail improvement at all three deadlines while preserving bulk MAE/MedAE and worst-error performance under predeclared noninferiority tolerances. Possible planning targets are a ≥0.05 tail-MAE gain, ≤0.01 bulk/median degradation and ≤0.02 CVaR95 degradation, with paired confidence bounds; these are **not selected acceptance criteria or results now**. Final tolerances and largest-error rules belong in the separate design freeze before forecasts. Calibration or a proper-score gain alone is insufficient. Train ordinary matched supervised/metadata controls first, then one justified mechanism with a conventional distillation/canonicalization control if relevant. Repeated exploration cannot consume the sealed TEST.

**Current decision:** carry out only the frozen lower-M metadata feasibility phase after its implementation/review freeze. Independent sequence counts, station support, waveform availability, final calendar selection and any training remain outstanding.
