# Source-only anonymous archive collector

`collector.py` provides pure `validate_plan(bytes)`, immutable `Plan`/`Slot`, a gated callable `collect(plan, exclusive_output_directory, ActualInvocationGate)`, and the invented-loopback-only `collect_fixture`/`verify_fixture_manifest` test interfaces. Importing performs no I/O. There is no actual input file reader, key mapper or ready-to-run acquisition CLI.

Focused verification:

```sh
python3 -m unittest -v test_collector.py
```

The tests use stdlib, invented keys and local HTTP only. Local socket binding may require sandbox permission; this does not permit a public data request. No installation is needed. See [PROTOCOL_v1.md](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_archive_transport_preflight_v1/PROTOCOL_v1.md) for fixed caps, fail-closed receipt semantics and byte/OS limits.

The input JSON has exactly `protocol`, `study_id`, `proposal_sha256`, `day_basis`, `mapping_provenance`, `slots`. Slots have exactly `slot_id`, `key`, `unavailable_reason`, in fixed order. Requestable keys use the nominal documented daily layout; unavailable slots have `key:null` and a reason. The source bytes, not a reformatted equivalent, define the roster pin. The test's `document()` constructs only invented examples; it is not an actual roster or mapping precedent.

Outputs are private: immutable roster, initial receipt, per-slot journals, body/partial files, final receipt and manifest. Do not place them in the public/reviewer packet. The parent must independently verify exact member hashes, roster/receipt links, deadline/budget accounting and run completeness before any future decoding. The fixture verifier proves invented local outputs only; no independent actual-result auditor has run or been authorized here.

Review uses the autoreview skill's default Codex engine on a separate isolated code-only snapshot. Source, invented tests, authored protocol and public test proof are allowlisted; actual inputs/IDs/keys/bodies/receipts, official raw source/headers and credentials are excluded. Preserve all other work. Stop source changes at the first clean review; any later change needs a new version/review freeze.
