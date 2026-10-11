# Independent final counts-plan replay

The final V4 plan passes **3,812 source-independent checks with zero mismatches**. An additional **288** checks recreate each current station mask after discarding all accepted picks at/after its own horizon; every mask matches. This one-off audit used only the standard library. It made no request, production import, sample-array decode, source edit, review, AWS, fit or Git action.

| Frozen quantity | Independent result |
|---|---:|
| Original eligible CMT frame / frozen lower sample / tail | 3,437 / 346 / 149 |
| Selected source events | 96 |
| Candidate TRAIN / DEV / TEST events | 41 / 24 / 31 |
| Selected Mw>=6 TRAIN / DEV / TEST events | 29 / 12 / 19 |
| Union station targets, all queryable | 411 |
| Station totals at strict +1 / +3 / +5 seconds | 202 / 317 / 411 |
| Fresh level=channel metadata GETs | 411 |
| Exact waveform cache hits | 9 |
| Separate cached level=response candidates | 9 |
| Waveform POST blocks / total new queries | 6 / 417 |

All 495 raw accepted-pick bases match the preserved outcomes, including byte-pinned original 149 metadata. The audit reconstructs the original CMT eligibility frame and frozen 346 sample before ranking the 96 roster. Every event record, accepted-subset clock, station representative, strict mask, target, channel query, cache decision and ordered POST body matches. Each block retains 16 source events, with uncached target counts 46/71/56/74/89/66 (402 total); nine waveform targets use frozen exact cache. The original 34-entry cache ledger retains two unsuccessful/empty nonhits and 14 successful unselected nonhits.

A real representative pick exactly at +1 second is excluded. The cap reaches eight for 5/14/25 events at 1/3/5 seconds. All 96 events have positive accepted NZ P evidence and nonempty unions. **Ten selected events have incomplete associated-P structure, all in candidate TEST.** Their clocks and source denominators stay unchanged. This is not a complete-clock exclusion or new gate.

[selection_provenance.json](selection_provenance.json) binds all 44 public promotion members, nine final sources, seven reviewed dependencies, 52-test/clean-V4-review evidence, exact Python/runtime package metadata, six bulk inputs and completed 495 independent verification. All supplied original metadata and cache manifest member hashes were checked. [selection_replay.json](selection_replay.json) retains coarse panels, cap histograms and six exact body hashes. Real identities and reconstructed request bodies remain under ignored local_runs.

The private input SHA256 is 23f39fb2f8222ee7b57c82ccdd502af8f8bdbaed6d8cfdbfd28e158b07473800; plan SHA256 is 491fdf5366c94e7dc4f3cc029b3d4493a24c521db79a2662bc0734d26fff6be6. Event-order SHA256 is f9255ff9cd0ade1d4e3d07ea7625df9dc1a5139d95367e6808df64d6a1d7c404.

The first auditor command referenced a nonexistent runtime receipt filename and stopped before raw replay. [selection_preflight_failure_v1.json](selection_preflight_failure_v1.json) preserves this auditor error; the corrected command verifies the actual runtime_receipt.json. No production source or scientific rule changed. Original preparation files remain byte-exact; their historical contextual hashes are not the final reviewed V4 freeze.

Passing preparation does not establish new channel/waveform acquisition success. Cache hashes establish provenance, not decoded counts or physical calibration. Retrospective accepted picks do not verify operational triggering, telemetry, the earliest fully resolved association clock, sequence-isolated support, trainability, method improvement, novelty or benchmark superiority. Parent-owned pushed freeze/acquisition and later completed engineering replay remain separate.
