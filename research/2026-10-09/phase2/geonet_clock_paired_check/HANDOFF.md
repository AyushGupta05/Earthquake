# Source-only handoff

Acquisition has not been run. No actual six-event roster or private plan was prepared in this producer task. All existing census/bulk/counts freezes and the source-only clock-completeness audit/proposal remain unchanged. This directory alone contains the new producer source. Parent handles actual private input preparation, independent plan replay, shared Git freeze/push and acquisition receipt.

Use the existing original-compatible Python:

    work/geonet_waveform_feasibility/.venv/bin/python -B -m unittest discover -s work/geonet_clock_paired_check -p 'test_paired.py' -v

After clean code-only review, prepare a new ignored input receipt under this directory's local_runs. Its version is `geonet-paired-selection-inputs-v1`. It must set `completed_bulk_independently_replayed=true` and `bulk_gate_passed=true`, provide `bulk_files` mapping the exact six original bulk relative paths to SHA256, and `bulk_independent_replay_path` / `bulk_independent_replay_sha256` for the already completed independent bulk verification in the bulk directory. No cache or alternate source is accepted.

    work/geonet_waveform_feasibility/.venv/bin/python -B work/geonet_clock_paired_check/paired.py prepare --inputs work/geonet_clock_paired_check/local_runs/selection_inputs_final.json --plan work/geonet_clock_paired_check/local_runs/planned_inputs_final.json

Do not replace the created plan. Have a separate auditor reconstruct the exact six roster, two controls, ordering, original pinned XML linkage/projection and twelve eventid-only requests without importing this producer source. Keep actual IDs, raw XML, query URLs, origin/pick IDs, rosters, plans and input/parent receipts private.

After actual independent replay and a separate pushed source freeze, parent creates `geonet-paired-parent-receipt-v1` under local_runs. Required true fields are `acquisition_authorized`, `code_only_review_clean`, `private_selection_independently_replayed`, `freeze_pushed`; required strings are40hex `git_freeze_commit`,64hex `private_selection_replay_sha256`, and exact `plan_sha256`. Copy exact plan bindings for `processing_files`, `reviewed_dependencies`, `runtime`, `input_receipt_sha256`, `bulk_input_pins`, `bulk_replay_sha256`, `event_order_sha256`, `specification`. The collector recomputes the plan before requests.

    work/geonet_waveform_feasibility/.venv/bin/python -B work/geonet_clock_paired_check/paired.py collect --plan work/geonet_clock_paired_check/local_runs/planned_inputs_final.json --receipt work/geonet_clock_paired_check/local_runs/parent_receipt_final.json --output work/geonet_clock_paired_check/local_runs/collection_final

One new exclusive run only: six source events x3 representations,12 fixed GETs,48MiB delivered bytes,4MiB each,360s outer including validation/imports,20s whole requests,1s minimum start spacing,10s finalization reserve. No retry, redirect, replacement or resume. A full twelve-attempt completion can include transport/unsupported outcomes and does not imply successful metadata recovery. A failure remains incomplete and is never relabeled as zero coverage.

Before interpreting results, independently replay actual request/manifest/body hashes and all18 representation slots, exact event/preferred-origin/arrival linkage, original/own/shadow clocks, native weight/use-flag mapping and revision-conflict exclusions. No automatic existing clock edit, model input, benchmark exclusion or novelty/improvement claim follows from this diagnostic.
