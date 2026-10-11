# First-clean source-only handoff

Frozen processing source is `auditor.py` (24,803 bytes), SHA-256 `26072a677afd5f46a4c16cc3f5d9d3d6bb8395d1186a3e1c0b0fc3a214bf7d96`. Invented tests are `test_auditor.py` (31,302 bytes), SHA-256 `8cadc740d00d066a4cd168026e65361cc9a485eec6d377419f6e18ab29f04ef0`.

All 39 invented test methods passed in the focused run retained as `review_evidence/test_review_fix_1.txt`. Codex autoreview attempt 4 exited 0 with findings `[]`; the structured receipt SHA-256 is `e8efd65723f3af2a5844fd0ebb4c27bd3819b9e1e41e333bc986ec3395f21f75`. Isolated full-source review commit is `f3119909f2771e8beb5863c44f93e9a8b8e2441b`, against empty baseline `fe55b55` (the full isolated baseline and review history remain excluded from the public allowlist). The default autoreview helper ran `--mode commit --commit HEAD --engine codex --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex --no-web-search --prompt-file .../review_evidence/review_prompt.txt`. Source edits and review runs stopped at first clean.

Attempt 1 failed Codex runtime initialization. Attempt 2 failed structured report validation because a finding path was absolute. Attempt 3 reported one journal-type equality defect; an invented reproduction demonstrated boolean/integer aliasing. The accepted fix preserves decoded JSON types, with three new regression methods. Failures, accepted-finding record and reproduction remain in the safe evidence packet. No findings were rejected. Parent retesting and pushed-source verification remain separate.

The final collector public schema/protocol/gate copies match its first-clean frozen pins exactly; `review_evidence/public_contract_binding.json` records the independent byte comparison and public clean-receipt pin. No collector implementation or actual inputs were read, copied or imported. Earlier semantic sources/freezes and the final nine-file archive mapping uncertainty packet remain unchanged.

Pure API:

```python
from auditor import audit
result = audit(
    plan_bytes, manifest_bytes, bounded_member_reader,
    execution_summary_bytes=summary_bytes,
    execution_summary_pin={"bytes": summary_count, "sha256": summary_sha256},
)
```

`bounded_member_reader(name, maximum_bytes)` returns exact bounded `bytes` or raises. Parent custody must independently preserve and pin the original plan, exact final manifest, separately serialized returned execution summary, and full private artifact inventory, and authorize bounded reads. The module verifies only declared fixed members and never lists or opens paths. JSON members/manifest are capped at 64 KiB, plan/summary at 16 KiB, bodies at 64 MiB each and 256 MiB total; the parent callback must enforce the bounds while reading. A missing/failed/mismatched final manifest or summary, any invalid evidence, or requestable unattempted slot yields zero qualified slots. Extant failures/partials must remain preserved.

A valid completed result contains `valid`, `finalization_verified`, `complete_accounting`, `all_slots_transport_pass`, `qualified_slot_count`, `attempt_count`, `observed_body_bytes`, `consumed_upper`, four fixed `slots` with `slot_id/status/transport_pass`, and `issues`. Values concern consistency of recorded transport evidence and exact retained bytes only. Repeated successful keys count in the four-slot denominator; attempts and byte totals count once. Unknown-length exact-cap completion and journal numeric-type substitutions are conservative exclusions documented in `PROTOCOL.md`.

`mapping_status` remains `unverified_hypothesis`; all seven scientific/mapping/coverage/failed96 claims remain false. `filesystem_inventory_verified` and `physical_timing_verified` are always false, and `preserve_parent_artifacts` always true. HTTP metadata and timing fields are recorded assertions, not independent wire/physical observations. No UTC filename, blank-location, NSLC/day, endpoint, miniSEED, waveform coverage, causal availability, EEW, model improvement, complete inventory or acquisition authority follows from replay.

Only files in `PUBLIC_ALLOWLIST.txt` are public. `.review_snapshot/.git`, caches and every actual/private artifact path are excluded. `MANIFEST.json` pins the safe reviewed source, copied contracts and evidence, while `SHA256SUMS.txt` pins the manifest and allowlist as well. Runtime/helper/Codex binary pins are in `review_evidence/runtime_pins.json`; no installs occurred. All safe files are read-only after freeze. No actual read or replay is authorized by this handoff; the parent owns the later pinned gate.
