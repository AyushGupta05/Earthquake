# V2 source-only review closeout

The first clean V2 result is attempt 03: default Codex, helper exit 0, `findings: []`, `overall_correctness: "patch is correct"`. Reviewed source, tests, protocol, schema and prompt were closed to edits at this result. Only this authored accounting, the copied final structured result and curated hash-list were added afterward. No extra review was run.

Focused tests: `python3 -m unittest -v test_collector.py`, Python 3.14.5, exit 0, 44 invented test methods, reported elapsed 19.942 seconds. Tests use fake transports and numeric-loopback HTTP only. They include maximum-size valid plan whitespace through both child envelopes, the absolute output-path bound, uncertainty/gate rejection, fixed slots and deduplication, retained errors/partials, declared and unknown-length caps, deadline cutoffs/finalization, request spacing, writer-exit confirmation and receipt/member hash checks. Exact proof is in `TEST_PROOF.json`; the reviewer independently inspected code but did not run tests or collection.

Review command, from the isolated `review_snapshot` directory:

```sh
/Users/ayush/.codex/skills/autoreview/scripts/autoreview --mode local --no-web-search --stream-engine-output --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex --prompt-file review_prompt.md --output ../review_output_03.txt --json-output ../review_result_03.json
```

The authorized runtime escalation supported this same source-only engine; it did not authorize data requests. Tools were read-only; web search was off. No engine/model override, installation, nested reviewer or panel was used. The explicit existing Codex binary has SHA-256 `0d5ac7aae20c4eda6242428d5e218c55ba96d8763fda2a271088ff37104b9d28`. Isolated local Git setup existed only to present these authored files as a dirty snapshot; shared/publication Git was untouched.

Attempt accounting:

1. Attempt 01 failed helper structured-result validation because a finding used an absolute `code_location.file_path` inside the snapshot. No validated structured report was saved and no finding content or clean result is inferred. The prompt was clarified to require bundle-relative basenames; the same engine and binary were retained.
2. Attempt 02 exited 1 with one P2 finding, accepted after inspection: the inherited 32,768-byte internal envelope could reject a legal 16,384-byte plan whose tab/newline whitespace expands when embedded in JSON. The validated report was 1,137 bytes, SHA-256 `f60792d276129e228a2e4b73a0e95eac3cf48f1a045995db56db271236d8e2f6`. Both internal envelope bounds became 65,536 bytes and the absolute output path was capped at 4,096 UTF-8 bytes; canonical invented-loopback endpoint syntax bounds fixture overhead. Two focused regressions were added and all 44 tests passed. Public plan/receipt fields, 16 KiB plan cap and acquisition byte/deadline limits were unchanged. The implementation bound is explicit in the reviewed protocol/schema.
3. Attempt 03 exited 0 with no findings. `review_result_final.json` is a byte-identical copy of this result: 481 bytes, SHA-256 `5bd153e3762faedb19849f9b65aa8d015ec57768f66720a778e4f75502de9107`. Nonblocking runtime icon/state/snapshot warnings did not change the helper outcome.

The frozen V1 curated packet was independently rehashed before V2 closeout and matched every entry, with no writable curated member. Its hash-list SHA-256 remains `56963137240819b0cdae1c699c3087eba64b9e96804b9eed6b545f2e7b7b9c69`. V1 source and every prior outcome/freeze remain untouched.

No actual input, private metadata/roster/key/body/receipt, official raw source/header, credential or AWS artifact was read. No public data/object/account request, installation, scientific decoding or fit occurred. Raw review output, caches, fixture outputs and isolated Git machinery are excluded from the curated packet. V2 permits only the explicit unverified literal-key transport hypothesis; all semantic/day/channel/location/endpoint/coverage/failed96-repair claims remain false. The actual-invocation gate is unsatisfied by this source task. The parent owns publication, immutable private plan, authorization and execution-summary/manifest/member custody; an independent result audit is required before any qualifying transport assertion.
