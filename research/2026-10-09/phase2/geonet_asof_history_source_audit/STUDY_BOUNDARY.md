# Defensible study boundary

Operational history fusion remains a no-go prerequisite claim: this audit has not verified an immutable, complete New Zealand issued/received catalog. A narrow retrospective study is possible only after its input artifact and availability assumptions are frozen and independently checked. No fit, acquisition or performance claim is proposed as a completed result here.

## Clocks and states

| Quantity | Meaning required in a replay | What it cannot substitute for |
| --- | --- | --- |
| Origin/occurrence time | Estimated physical event time in a particular version | When the event was detected, published or received |
| Resource creation | Author/provider creation of that resource | Public server visibility or consumer delivery |
| Modification/update | Revision time with documented provider semantics | First issuance; all earlier revisions; receiver time |
| Provider issue/publication | When a particular payload became available at a defined interface | When the intended EEW consumer actually received it |
| Consumer receipt | Locally logged arrival of identified bytes under a recorded clock | Ground-truth occurrence or completeness of events never received |
| Snapshot/commit | Identified content at a catalog archive boundary | All intermediate versions, publication merely from Git author/committer dates, or receipt |

The EEW deadline must be defined at the inference consumer. A waveform sample's timestamp, an offline associated P pick and a live trigger/receipt clock are different quantities. This task does not replay an operational picker or network delivery. If the same older catalog snapshot is used at 1/3/5 seconds, its availability must precede the earliest deadline; the three predictions still require genuinely prefix-restricted waveform inputs.

## Narrowest useful fallback: a global history prior

Start with a **single frozen older background snapshot**, using a fixed region/population definition that does not require the current target's unknown location. If a suitable provider snapshot can be shown to have been published before the entire evaluated period, this avoids rapidly changing catalog state and unknown current query coordinates. Archived publication alone supports an availability assumption, not verified receipt by this particular EEW consumer. A receiver-log study would require separate authorization and collection.

For a magnitude-only waveform posterior `q0(M | W_d, A_d)`, the proposed research control is

`qH(M | W_d, A_d, H) ∝ q0(M | W_d, A_d) × πH(M | A_d, H) / π0(M | A_d)`.

`W_d` denotes exactly the current waveform prefix, `A_d` the same detection/selection population, and `π0` the effective TRAIN magnitude prior after sampling/weights/eligibility. Normalize once on compatible support. The global-history candidate avoids a plug-in target hypocenter and does not inherently require a joint `q(M,z)`. It still assumes the conditional waveform likelihood given magnitude and selection is unchanged by history. History-dependent location mixtures, sensor availability, overlapping events or detection can break that assumption; a global ratio does not repair them.

The candidate history prior is not automatically a fit to catalog magnitude frequencies. Catalog inclusion and EEW detection are different selection mechanisms. In principle `πH(M | A_d,H)` also depends on detection probability, with unknown location and network state integrated out. Without a justified selection model or matched detected cohort, interpret a frequency-based ratio as a retrospective heuristic and test its failure modes. Do not substitute an arbitrary Gutenberg–Richter prior for the trained model's effective prior, multiply two posteriors without correction, or multiply nested 1/3/5-second full-prefix posteriors as independent evidence.

This global control is a narrower alternative to location-conditioned MAGNET adaptation, not a performance result. A learned global prior may ultimately be unnecessary if a fixed TRAIN prior or a simple rolling frequency/GR control does as well.

## Retrospective availability tiers

1. **Final-history mechanism study:** truncate a present-day final catalog by occurrence time. Label it retrospective final-estimate context; it does not establish historical availability. It can test whether the input class merits further work, with strong leakage caveats and no operational claim.
2. **Older archived-snapshot study:** freeze an exact historical snapshot preceding the evaluation period, with verified historical publication evidence and all artifact hashes. Daily SCEDC versions are a lead for this tier in southern California, not yet verified inputs and not evidence about GeoNet coverage. A fixed old snapshot sacrifices recent sequence context but narrows the availability requirement.
3. **Provider-version pseudo-replay:** use complete reconstructable provider versions before a documented issue boundary. Creation-time truncation plus an assumed delay is a sensitivity analysis, not measured publication or receipt. Freeze delays prospectively and report them as assumptions; never tune them on TEST.
4. **Consumer-receipt replay:** reconstruct catalog state from an append-only log of received bytes, aliases/merges/deletions and delivery failures. This could support operational availability when clocks and waveform receipt are also audited, but neither an existing usable archive nor a complete detection population was established here.

## Population uncertainty and matched controls

Retain a fixed target denominator independently of history availability. A missing historical version is unknown, not an empty seismicity history. A final catalog may omit later-deleted events or include retroactively discovered events; filtering final occurrence times cannot recover those cases. Preserve cancellation, reassociation, revision and unknown-state counts. Excluding the target needs version-aware aliases and an explicit source-state rule; matching only today's preferred identity can miss an earlier alias.

Compatible magnitude types/scales, threshold/truncation and uncertainties must be specified. Do not silently equate ML, Mw and CMT labels. Sparse tail-selected current CMT history is not a complete regional background catalog. Catalog completeness can vary over region, time, magnitude, processing policy and busy sequences; absence from that catalog cannot demonstrate absence of recent seismicity. Weighting a chosen research sample cannot reconstruct unobserved or unpublished events.

Freeze identical target splits, waveform clocks, baseline weights and support across: unchanged waveform model; identity-ratio control; TRAIN-only global prior; older frozen global history; simple rolling global frequency/GR; learned global history; final-history retrospective oracle; fixed assumed publication-delay sensitivities; and history permutation using only TRAIN/DEV design decisions. Location-conditioned candidates belong in a separate extension with unknown-location uncertainty and compatible detection conditioning. Report each horizon, high-magnitude error, overall MAE/median bias, worst-error quantiles, calibrated probability scores and uncertainty with event/sequence blocks. Density improvements do not establish tail point-error improvement. No current results or thresholds are invented by this source audit.

## Go/no-go prerequisites

Before any real history experiment, obtain authorization for the specific artifact/source and freeze: source/version bytes and checksums; historical publication evidence or explicit retrospective assumptions; format/license; catalog coverage and update/deletion/alias semantics; declared clocks and time zones; magnitude compatibility and effective TRAIN prior; target exclusion and fixed denominators; selection/detection limitations; candidate support and likelihood-stability assumptions; matched control/evaluation protocol and sealed TEST policy.

Before an operational claim, additionally verify received-byte logs and clocks, complete reconstruction across delivered revisions and failures, a real trigger/transport replay, and the target detection population. This audit supplies documentation leads, not proof that these prerequisites are satisfied.
