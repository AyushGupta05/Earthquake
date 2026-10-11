# Joint invocation V3 source-only handoff

This is a NEW separately versioned wrapper. It is not an actual invocation or
actual-input authorization. Existing V1/V2 source, review, manifests, failed
artifacts, event selections and clocks remain unchanged.

V3 changes only protocol identity to `geonet_legacy_joint_invocation_v3`, precise
bounded serializer_failure classification, and child/supervisor output caps to
33,554,432 bytes including newline. 32 MiB is a separate parent decision, not
proof that output size caused the parent-reported V2 serialization ValueError.
The packet has read no actual input or receipt. No result size, scientific
success, novelty or operational claim is made.

Use PROTOCOL.md and SCHEMAS.json as the exact public contracts. The child failure
line has seven exact fields: protocol_id, complete:false, fixed stage,
validated_body_count 0..18, body_index:null|0..17, finite exception_class and
serializer_failure. The latter is `not_serialization`, `output_cap_exceeded`,
`json_encoder_rejected` or `other_or_unknown`. Only exact internal markers
classify cap/encoder failures; no exception strings/values/IDs/paths/XML or
arbitrary exception class names are exposed. The entire stderr diagnostic line
stays at most 1024 bytes. Count means body path/hash/length/budget validation,
not parsed or scientifically accepted records.

All four scientific implementation pins remain literal:

| File | SHA-256 |
|---|---|
| projection.py | ee4a3fe78681ee0fb0928306ae821d5b964765c1a2c414c77b448d2c8bf0d097 |
| comparison.py | 9c0b3c3480a345ecb53ac6e52b18bc47657b4792ce527b6b640d3adc230caab6 |
| shadow.py | a9d4c5f33ea831cbdbd815f960c641153f350ec267daa706aa8bedaa87999bcf |
| semantic_audit.py | cc93594acb6c120319d6520b17c7f2e2cdaad86ed4ae5d0de6115dfc58921763 |

Fixed six-event/eighteen-body semantics, input/source caps,120-second watchdog,
process-group termination, no requests/no RSS ceiling claim, exclusive outputs,
private/public result separation and normal-return+complete-receipt proof are
inherited unchanged. No fallback, resume, truncation or hidden partial promotion.

The public_dependencies directory contains all 120 exact source-only members,
including the three generic producer companions omitted by V2's top-level
publication list but already byte-pinned in its reviewed source-bundle mapping.
V3's manifest/allowlist/copy closure includes those companions. This is packaging
only, not a scientific change or explanation of the actual V2 failure.
Original V2 publication artifacts are not edited.

Focused test command:

```
/opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -B -m unittest discover -s ABS_V3_PACKET -p 'test_*.py' -v
```

All49 previous invented test methods are retained with V3 identity/diagnostic
adaptations. Eleven added methods cover exact/over 32 MiB output, nonfinite/cyclic/
unsupported JSON, message-spoofed or unknown/buffer failures, safe diagnostics,
and all 120 real frozen public members through invented integrated inputs. See
test_receipt_v2.json and tests_v2.txt for executed test results. runtime_pins.json
pins Python, autoreview helper and the unchanged default Codex CLI. Review is
code-only, no-web, default Codex/same binary to first clean; review receipts bind
the exact source snapshot. No reviewer may read actual/private artifacts.

Only safe_to_promote_paths.json entries are eligible for later public source
handoff. Review-snapshot Git, fixture files, source-preparation scratch, and all
actual plans/authorizations/inputs/receipts/results remain excluded. Parent
independently verifies allowlist closure and every listed pin before publication.

Callable remains `supervisor.supervise(runtime, runtime_sha256, child,
child_sha256, supervisor_sha256, plan, plan_sha256, authorization,
authorization_sha256, out_dir, max_seconds=120)`; out_dir must not exist.
A NEW parent-private plan/authorization must use the V3 protocol ID and fresh
wrapper/source/runtime/review/test pins plus a separately pushed V3 freeze.
No old authorization is a V3 grant. Parent preserves the exact original six/
eighteen selection/order/body/source caps/clock bindings. Actual invocation is
root-owned and must occur only after a new first-clean pushed freeze and private
gate; this source-only task grants none. No automatic followup exists after 32 MiB.

A public aggregate is eligible only if supervisor returned normally (CLI exit0)
AND its private receipt is complete with independently verified result hash and
termination/time bounds. A candidate file or safe failure diagnostic alone never
qualifies. Root alone owns the subsequent new private gate and any aggregate
adjudication. Further processing edits require another reviewed version.
