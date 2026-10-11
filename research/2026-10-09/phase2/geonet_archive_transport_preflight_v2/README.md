# Source-only literal-key transport collector v2

`collector.py` provides pure `validate_plan(bytes)`, immutable Plan/Slot, gated callable `collect(plan, exclusive_output_directory, gate)`, and invented-loopback-only `collect_fixture`/`verify_fixture_manifest`. Importing performs no I/O. No actual input reader, key mapper, ready-to-run acquisition CLI or scientific decoder is included.

V2 permits only an explicitly preregistered `unverified_hypothesis` for literal nominal keys. It retains the V1 numerical limits and failure handling while avoiding a fabricated mapping-verification assertion. V1 and every older outcome/freeze remain unchanged.

Focused verification uses stdlib and invented numeric-loopback HTTP only:

```sh
python3 -m unittest -v test_collector.py
```

No installation is required. Loopback permission does not permit a public request. Production source is gated separately by [ACTUAL_INVOCATION_GATE.md](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_archive_transport_preflight_v2/ACTUAL_INVOCATION_GATE.md). See [PROTOCOL_v2.md](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_archive_transport_preflight_v2/PROTOCOL_v2.md) and [SCHEMA.md](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_archive_transport_preflight_v2/SCHEMA.md) for caps, clock/byte limits, private-output contracts and required parent execution-summary custody.

Default Codex autoreview uses an isolated source-only snapshot. Actual data/IDs/keys/receipts/bodies, official raw sources/headers and credentials are excluded. Stop source changes after the first clean result; later changes need a new reviewed version. The parent owns pushed freeze and any later actual invocation; this task performs neither shared Git publication nor acquisition.
