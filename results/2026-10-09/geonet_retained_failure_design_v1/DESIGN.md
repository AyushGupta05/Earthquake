# Retained-failure offline diagnostic: design V1

This is a documentation-only recommendation for a NEW ENZ diagnostic V4, not an implementation or invocation authority. It can give a useful terminal account of the fixed cached evidence even when some transfers failed. It cannot establish physical waveform availability, usable model input or magnitude improvement. Root's separate [normative V4 proposal](../geonet_retained_failure_qualification_proposal_v4/PROPOSAL.md), SHA-256 `cf29847b2c7529b6f12de8365a06c734d11fceff5b5bf51a1500134e6cd93b60`, now adopts these states. Source and invented tests still require review, publication of the freeze and a fresh private one-invocation authorization.

Root reports that the sole horizontal V5 run passed final transport accounting with eight attempts, six transport-qualified HTTP200 bodies and two complete HTTP404 error bodies. This task has not inspected or independently replayed those private artifacts. The old ENZ V3 all-eight-pass gate remains unsatisfied; this recommendation does not authorize that version or reinterpret its results. The frozen [ENZ V3 protocol](../geonet_archive_enz_precontext3_qualification_v3/PROTOCOL.md) and [transport auditor V4 protocol](../geonet_archive_transport_independent_audit_v4/PROTOCOL.md) are context only; exact pins are in SOURCE_PINS.json.

Preserve the four ordered ordinary/higher/boundary/final roles, original clocks and 3TRAIN/1DEV selection. Retain literal E/N/Z per original parent slot without aliases or new acquisition. For exact integer p=3 and h in 1,3,5, diagnose `[original t0-3s, original t0+h)`. Retain all 36 component and 12 joint cells, including failures; do not require all 48 cells to be available before an invocation can be complete.

Component eligibility must precede the prefix predicate. A candidate body needs parent-verified transport provenance, bounded byte/hash custody, supported header/full representation agreement, expected literal NSLC, a supported consistent observed rational rate, and valid decoded representation. A wrong decoded identity does not establish absent expected-channel recording. Identity/rate/representation uncertainty, unsupported decode and unqualified transport all produce UNKNOWN, rather than known-false. Error bodies are retained for custody only and never scientifically decoded. Eligibility is not response, physical axes, metadata-rate or calibrated timing validation.

Only an eligible component may inherit the unchanged core's true/false/null prefix predicate. False means that this validated decoded representation fails the declared local prefix predicate; it does not mean physical absence. Whole-object identity/rate checks are structural conditions, not causal prefix features. Amplitude/finite screens remain cropped to the horizon, so later amplitudes cannot change an earlier cell. The unchanged rational core and runtime pins are inherited as proposed dependencies, not executed here.

For each fixed slot and horizon apply this ordered rule:

| Component evidence | Joint state | Common rate/lattice fields |
| --- | --- | --- |
| At least one eligible component is false, even with another unknown | FALSE / incomplete | null / null |
| No eligible false and at least one unknown | UNKNOWN | null / null |
| All three eligible components true; observed rational rates differ | FALSE / incomplete | null / null |
| All three eligible components true; same rate but incompatible lattices | FALSE / incomplete | common rational rate / false |
| All three eligible components true; same rate and compatible lattices | TRUE / available | common rational rate / true |

Thus false can dominate unknown for the joint conjunction while the unknown component remains recorded. A two-component rate or phase mismatch with the third unknown cannot trigger a common-grid failure. Common-grid testing occurs only after all three eligible component cells are true. An eligible core null remains unknown.

Catalogue `pick_ns < t0+h` remains a separate strict diagnostic with signed offsets; neither a nonnegative-delay filter nor a pick cutoff gates decoded-grid eligibility. Report pick counts over all four slots and their availability intersection separately. Preserve no merge, repair, interpolation, padding, deduplication, re-clock, response correction, fit or replacement. Returned ObsPy traces do not certify raw record boundaries or timing, even when the wrapper performs no merge; see [DEPENDENCY_NOTE.md](DEPENDENCY_NOTE.md).

A terminal result should distinguish complete bounded execution from scientific true/false/unknown cells, preserve every transport failure and stop. It is not a repaired acquisition, a coverage estimate, an operational clock measurement or a new model result. The prospective field and authorization recommendations are in [PROSPECTIVE_SCHEMA.md](PROSPECTIVE_SCHEMA.md) and [GATE_RECOMMENDATION.md](GATE_RECOMMENDATION.md).
