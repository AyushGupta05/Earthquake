# Code-only auditor handoff

First clean default Codex autoreview: review12, helper exit0, no findings. The reviewer performed static inspection; our existing verified runtime passed56 invented-only tests separately. Source is frozen to [source_freeze.json](source_freeze.json) and the exact [review bundle](review_bundle_manifest_v11.json). All earlier validated findings, infrastructure failures, the unavailable path-validation report and the one repaired fixture-edit failure are retained. No further review or source change follows this first clean result.

| File | SHA256 |
|---|---|
| auditor.py | 7760a14ef895ecf6f15809893725b37eb59d932364a5425ac8eb8faebbf9d7c3 |
| test_auditor.py | a46be1f0f185941763bb80ee473fe6bdf13c283df8886ecf180be6c38c54acd0 |
| CONTRACT.md | b785503f49d4a3e4b22c26b202735ea825ec7e9c777252d9c6bbe4bf2b4de6d9 |

[Tests receipt](tests_receipt_v11.json), [clean report](review_v12.json), [exact review command](final_review_receipt.json), [advisory resolution](REVIEW_RESOLUTION.md) and [read-scope ledger](source_access.json) provide the code-only evidence. The [autoreview skill](/Users/ayush/.codex/skills/autoreview/SKILL.md) was applied with the same default engine, no web search and an isolated ephemeral Git repository; no shared-repository Git action or software installation occurred.

The focused command, from this auditor directory, was:

```sh
MPLCONFIGDIR=/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_counts_result_audit/.runtime-cache/matplotlib /Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_waveform_feasibility/.venv/bin/python -B -m unittest -v test_auditor
```

Existing Python3.14.5/ObsPy1.5.1/NumPy2.5.4 and23 approved package versions/locations were verified in source_access.json. Native miniSEED2 factor/multiplier and Blockette100 clocks, strict prefix edges, epoch joins, current-station masks, shared64MiB accounting, incomplete rejection and resource/provenance failures use invented fixtures. Both representations of100/3Hz exclude the NaN sample exactly at6seconds. Full-SEED/miniSEED3 forms are unsupported here and fail without recovery; this source does not certify them.

## Parent's only next actual-data call

The parent reported acquisition exit1/child exit2 with completed=false and artifact_pins_incomplete=true after a timeout. This subagent did not open that manifest, outputs, plans, receipts, real XML/miniSEED or native logs. No availability, calibration or model result is inferred from the failed run.

After independently checking the frozen source and rerunning invented tests, the parent may bind its private run root and already-loaded private manifest and call exactly:

```python
import auditor

auditor.verify_completed_files(private_run_root, private_manifest)
```

For the parent-reported incomplete fields this must raise `auditor.AuditError("completed parent exit0 required")` before any manifest member body is read. That narrow rejection is the entire actual-data handoff. Do not decode, reconstruct scientific outcomes, repair completion, resume, retry, run a further audit or publish raw artifacts from this handoff. No additional actual work was performed here.

## Evidence limits retained

The frozen producer remains unchanged. Short flat-prefix candidacy differs between its core and prose; future malformed metadata and missing per-response native-warning assignment can prevent equivalence. Missing exact rational-clock fields or scientific claim flags remain explicit private discrepancies. Optional full-response availability remains distinct from counts and never proves a calibrated physical prefix. Orchestration prerequisites and public aggregate/private-evidence separation remain in the frozen CONTRACT.md. This code preparation establishes no benchmark availability, operational EEW, independence, trainability, accuracy improvement, novelty or superiority.
