# First-clean source-only independent configured-key auditor v2

Frozen source is `auditor.py`, 24,815 bytes, SHA-256 `d2f8f4a1a744bc9fce432d3b62809b5d5c3f0da8bc92b4fb226bea25235a4251`. Invented tests are `test_auditor.py`, 35,377 bytes, SHA-256 `09b3fb867a54a60fb43ac5907ed0a3299259b63eb34bdef0108eca92547651b4`.

All 45 invented test methods passed in 0.199 seconds: the prior 39 plus six configured-order, source/profile-pin and legacy-identity regressions. The focused test receipt `review_evidence/test_bound_contract_1.txt` has SHA-256 `71be16ed69a1d2258f3d16d0be6bfa61c26b1f23f29f67e1babbd083adf01eaf`. Codex autoreview attempt 1 exited 0 with findings `[]`; structured receipt `review_evidence/review_v1.json` has SHA-256 `6ee3b7853045d7df614fc92b614fed4fcf28d385c4c4c8b5bf757932b77cf3c2`. No findings were accepted or rejected. Review was static; focused tests were run separately. Source edits and review runs stopped at first clean.

Isolated full-source review commit is `53ae2d999641e6a85a38a82be60651a389e9c887`, empty baseline `097e82049c5a7d8481036945772b10aa6b435160`. The authorized default helper command used `--mode commit --commit HEAD --engine codex --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex --no-web-search --prompt-file .../review_evidence/review_prompt.txt`; Codex runtime permissions used the previously established authorized runtime exception. An optional preparation-only prompt append failed because its copied frozen generic prompt retained read-only mode; that failure is preserved. Review used the unchanged applicable source-only custody/bounds/relative-path prompt and complete new source/docs/tests. No extra review was run for that preparation failure.

The frozen collector V3 public schema/protocol/gate copies match its first-clean pins: schema `6b8c490f1238e0bc8431fcbd8669c4e561029f3e63b871126fc8e39079e9f5f5`, protocol `162e368df0b0554804221222bb50a261333fec8e29b601f7de4e81a8feff518f`, gate `8057b18d925d5383ac3dd54e9827df1f639f020512eb317310d6bdac0f4aa2f9`. Separate binding metadata records the exact public byte comparisons and supplied collector clean-receipt pin. The six `public_writer_docs/` files are a pin-matched authored curated subset of the final writer-source packet, excluding raw third-party sources, headers, HTML/API responses and unneeded ledgers. No collector implementation or actual inputs were read, copied or imported. Selected frozen v1 source/test/manifest/allowlist pins remain unchanged; no old tests/reviews were rerun.

The NEW hypothesis binds proposal `574eaf45f17987bc4e78b212481748ec1392ed08493eeeef6d13700bd485c679`, raw config source `3194fa79e8993b99f0514239d7735dc4461b9d31aefd031b2f43e725612b6412`, uncertainty audit `d3f826d1b1e45c59fdd5760dc3b5e9f0a8e954a60c2ec7ee628e80031462ec74`, protocol `geonet-anonymous-archive-transport-v3` and hypothesis `anonymous_official_configured_literal_key_gets`. The authored profile hash `7031bb9cdb97d1c1463bd0b2f8527bf4fbbec279d81e37d836003a687e98e5da` is distinct and adds no plan field. Keys must follow `waveforms/miniseed/YEAR/YEAR.DOY/STATION.NETWORK/YEAR.DOY.STATION.LOCATION-CHANNEL.NETWORK.D`: directory and final filename NETWORK repeat; LOCATION is independently literal before the hyphen. The old tutorial order/protocol/pins and aliases are rejected. This is source-supported syntax, not deployed archive mapping proof.

Pure API:

```python
from auditor import audit
result = audit(
    plan_bytes, manifest_bytes, bounded_member_reader,
    execution_summary_bytes=summary_bytes,
    execution_summary_pin={"bytes": summary_count, "sha256": summary_sha256},
)
```

`bounded_member_reader(name, maximum_bytes)` returns exact bounded `bytes` or raises. Parent custody must independently establish full private artifact inventory, preserve/pin the original plan and exact manifest, separately serialize/pin the outer returned execution summary, and authorize bounded reads. The module verifies only declared fixed members and never lists/opens paths or makes transport requests. Plan/summary are capped at 16 KiB; manifest/JSON members at 64 KiB; bodies at 64 MiB each and 256 MiB total. The parent callback must enforce bounds during reading; checking returned bytes cannot constrain callback behavior.

Results use audit identity `geonet-independent-archive-transport-audit-v2`. Missing/failed/inconsistent final evidence, invalid values or requestable unattempted slots qualify zero slots and retain parent preservation. A valid completed replay returns transport flags, attempt/body totals and four fixed slot statuses. Exact duplicate sharing remains a generic capability; the narrower actual proposal's four distinct event/key slots, three TRAIN/one DEV/no TEST, fixed roles/reference clocks and acquisition authority are parent assertions, not inferred here. Prior four errors, failed96, selections, outcomes, clocks and every earlier source freeze remain unchanged.

`mapping_status` stays `unverified_hypothesis`; all seven mapping/scientific/coverage/failed96 claims remain false. `filesystem_inventory_verified` and `physical_timing_verified` always remain false; `preserve_parent_artifacts` is always true. Recorded HTTP/framing/policy/timing evidence is not independent wire/physical observation. No UTC archive partition, LC storage, channel identity, endpoint/key correspondence, miniSEED/day/coverage, causal availability, EEW, model or inventory-completeness proof follows.

Only `PUBLIC_ALLOWLIST.txt` files are public; `.review_snapshot/.git`, caches, raw external sources, collector implementation and all actual/private artifacts are excluded. `MANIFEST.json` and `SHA256SUMS.txt` pin safe source/docs/test/review/runtime evidence. Allowlisted files are read-only. Parent synthetic retesting, source publication, pushed freeze and the later bounded actual gate remain separate; this handoff grants no actual read or execution authority.
