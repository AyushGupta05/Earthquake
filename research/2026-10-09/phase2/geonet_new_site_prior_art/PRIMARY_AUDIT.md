# Targeted site and probabilistic EEW prior-art audit

Audit date: 2026-10-11. Scope: two named primary works and legitimate public author versions. No waveform/metadata rows, response inventories, checkpoints, code execution, requests for private copies, purchases, training, reviewer submissions, AWS or Git actions. The earlier spectral audit is unchanged.

**Decision:** broaden the prior-art exclusions; authorize zero new fits from this investigation. Site correction and physical preprocessing followed by probabilistic magnitude inference are already occupied ideas. Neither recovered source establishes a matched rare-high-Mw improvement at our first-network-P 1/3/5-second clocks. A full site-transfer descriptor would be a different input from our completed nominal gain/unit and static SITE controls, but it is an established nuisance observable, not an earned new mechanism.

## Primary-source capsules

All paper-derived substantive prose is confined to these capsules; the access ledger stores locators and access status rather than duplicating their content. Links identify the exact supporting version. Interpretation below is this project's reasoning, not additional claims about the papers.

### L: Lavasani, Heidari and Mirzaei

Published 9 January 2026, Acta Geophysica 74:53. The subscription preview describes predominant-period magnitude estimation, Fourier site correction and an inverse IIR using H/V-estimated site response, claimed phase preservation and faster computation. It reports Japan 1998–2022 and approximately 0.1–0.2 magnitude-unit improvement, without an accessible metric definition. Abstract: K-NET; data/resources: KiK-net. That provenance discrepancy remains unresolved. Exact post-P duration, magnitude scale, cohort/split, independent tail counts, filter/state/noise specification and H/V-estimation chronology were not recovered. Scoped title/DOI/author searches found no accessible full author manuscript or code. The preview cites a 2021 predecessor on removing surface-record site effects. No broad site-correction novelty claim survives; its headline gain is not a matched benchmark. [Publisher preview, abstract, data/resources and references](https://link.springer.com/article/10.1007/s11600-025-01766-4).

### T: Thapa and colleagues

Journal published 20 February 2026; full text unavailable; data availability: “Not applicable.” Author v1, posted 15 September 2025, is a public 31-page CC-BY4.0 preprint explicitly linked to that journal; versions were not compared. It combines U-Net++/attention/Gaussian P-labels with displacement-energy Markov/MCMC inference (pp.4–10). Equations12–14 sum displacement-squared energy over the signal duration;15 gives generic acceptance odds. Page11 asserts STEAD M3–8 and station-disjoint 70/15/15 splits; event independence and manifest were not verified. Table2 (p.19) pairs MAE .35/.31/.28/.21 with Hi-net/STEAD/INSTANCE/authors' cohort respectively: a cross-dataset comparison. Figure11 (p.26) uses P–S timing. Strict first-P 1/3/5 clocks, reproducible prefix likelihood, harmonized Mw labels, independent high-tail metrics and public code were not recovered. Computational latency does not establish observation duration. [Public author v1](https://assets-eu.researchsquare.com/files/rs-7479899/v1_covered_72941a4e-350f-410b-b336-dd982be57e51.pdf?c=1771862527), [journal preview](https://link.springer.com/article/10.1007/s10518-026-02403-1).

Page numbers in T refer to printed manuscript pages; the PDF has one preceding cover page. The PDF text was accessible, but three attempted rendered-page fetches returned cache misses; claims above rely on explicit parsed text, not inspection of plotted traces. No PDF bytes were downloaded or assigned a fabricated content hash.

## Consequences for our completed controls

The completed instrument study supports an association with nominal instrument gain/unit and station features on its reused validation cohort. It does not prove removal of a frequency-dependent ground-site transfer. A nominal hardware response R and a ground-site response S are different parts of a possible observation model. In an illustrative linear model, counts satisfy y = R*S*u + n, with u itself depending on source, propagation and radiation. Identifying S from y alone is not the same problem as correcting known R. The earlier response-state audit already excludes treating an invertible deterministic conversion of the same observations as new information.

Consequently the L capsule narrows our interpretation without making the scalar SITE experiment a replication. We can say that the existing station descriptors helped that experiment; we cannot relabel the result as a new causal site-removal method, or as evidence that a full site curve must help rare large events. The T capsule likewise excludes presenting physical preprocessing plus a sampled magnitude distribution as a distinctive contribution. A sampler is a numerical procedure: it does not supply a new observation, specify an identifiable likelihood, or guarantee noise robustness.

Neither source resolves our pending unknown pre-P hardware/filter state or proves a source-invariant posterior with correctly transformed noise. Lack of such verification is an access and specification limit, not proof that the authors omitted it. Nor should it prevent an ordinary supervised counts benchmark using available metadata and transparent causal preprocessing.

## What observable could actually differ?

An independently measured, dated station site-transfer curve, or contemporaneous collocated surface/borehole observations, would add nuisance information beyond our current nominal hardware fields. We have not established that either exists for the proposed GeoNet cohort. Computing a ratio from the event prefix alone does not magically identify the site's full transfer function. In particular, an amplitude-ratio curve cannot determine phase uniquely: multiplying a candidate transfer by an all-pass factor preserves its frequency magnitude. This is an algebraic ambiguity, not an allegation about L's implementation. Finite available pre-P state and stable inverse-filter assumptions also matter for a physical interpretation.

For an ordinary engineering comparison, a reliable historical site descriptor could be used without asserting exact physical deconvolution. If that descriptor is independently available later, the smallest useful comparison is:

| Arm | Same observable inputs | Question |
|---|---|---|
| Direct nuisance control | Raw causal counts, nominal response fields, full site descriptor, available pre-P context and validity masks | Can a flexible supervised head use the descriptor directly? |
| Deterministic correction control | A fixed causal regularized correction of that same prefix, plus the identical descriptor/context/masks and an amplitude-preserving path | Is the known conversion useful as representation/conditioning? |
| Physical interpretation, if earned | Same inputs with an explicit initial-state and transformed-noise model | Does a verified observation model improve probability calibration beyond the first two controls? |

These are conditional controls, not instructions to collect data or launch fits. Historical descriptors must come from dated external pre-event measurements or TRAIN-only estimation, with out-of-fold construction where their fitted values enter TRAIN examples. No DEV/TEST suffix, magnitude, station outcome, or unavailable later pick can build a descriptor. A common capacity/support density head must represent Mw through at least8.0 and use the same point decision. Every arm receives the same current-station set, actual available prefixes and first-network-P 1/3/5 clock; station identities appearing later remain hidden earlier. An inversion must not add a later window, secretly standardize away amplitude, or erase its transformed noise/state assumptions.

The discriminating claim would be a representation benefit or improved nuisance robustness. It would not be an information gain when all arms observe the same prefix and descriptor. Stronger physical invariance claims require a independently checked observation model; those requirements do not attach to every counts-engineering baseline.

## Present disposition

No new observable has been verified for this cohort, and neither capsule earns a new high-tail mechanism or an implementation request. Continue the existing modest counts/clock feasibility work. Preserve ordinary site-metadata and causal-filter baselines as prior-art controls if the relevant inputs become available independently. Any eventual empirical claim needs event-disjoint, sequence-audited evaluation of bulk MAE/MedAE, high-Mw MAE, CVaR95 and proper scores on identical evaluable events, with retained failures and uncertainty on scarce large-event counts. Compare with these papers qualitatively until duration, labels and cohorts can actually be matched.

Local context read: [completed instrument scientific audit](../../outputs/earthquake_instrument_scientific_audit.md) and [causal response-state audit](../causal_response_mechanism_audit/AUDIT.md). Their exact input hashes and the source-access attempts are recorded in source_access.json. This report contains no benchmark-superiority or novelty claim.
