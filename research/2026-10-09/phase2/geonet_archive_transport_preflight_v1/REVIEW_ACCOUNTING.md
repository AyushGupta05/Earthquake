# Code-only review and freeze accounting

The separately versioned source-only collector is ready for parent source/protocol review. **Actual input reads, key mapping, bucket/account requests and acquisition remain unauthorized and unperformed.** The first clean default Codex review ended with exit 0, no findings and `patch is correct` (confidence 0.87). Source, tests, protocol, gate and review input are unchanged after that clean result; only final review/accounting/hash-list metadata and read-only permissions close out this freeze.

| Attempt | Outcome and retention |
|---|---|
| 01 | Default Codex launcher failed before review: ENOENT for the Hermes npm vendored Codex executable. No review judgement or structured receipt was produced. This authored record preserves that observed infrastructure failure. No installation or reviewer-engine change was made. |
| 02 | Default Codex through the installed app binary returned exit 1 with two P2 findings; both were verified and accepted. Local source-only `review_result_02.json` is retained, SHA-256 `7343b4f81cf86864a2569ad64f583713ce766b21b0018d770dd72ac23aef095e`. |
| 03 | Same default Codex engine/binary and narrow scope returned exit 0 and no actionable findings. The exact structured result is copied to curated `review_result_final.json`, SHA-256 `fbb0eb00d663136831f6ed6cbf9bbdfd85d446587d037fe4dce81d66b98af7d7`. No additional review was run after this first clean result. |

The accepted partial-body finding concerned hashing before a killed worker had exited. The fix confirms writer termination within the remaining whole-run budget before any body pin; unconfirmed termination leaves accounting incomplete and preserves extant initial/journal/partial artifacts. The accepted spacing finding concerned an earlier timestamp than the recorded request start. The fix spaces from the previous returned request start. Three added invented tests exercise delayed kill/exit confirmation, no pin after unconfirmed exit, and uneven preparation delay before request starts. These findings and failed attempts do not alter any prior acquisition outcome or frozen proposal.

The final focused command was `python3 -m unittest -v test_collector.py`: **38 tests, exit 0, reported 19.374 seconds**, using only invented fake/numeric-loopback HTTP fixtures. Python 3.14.5 was independently checked with the same execution permission lane. The earlier 35-test passing run preceded the accepted fixes. Initial sandbox local-socket binding denial was handled by an authorized loopback-only rerun; it did not authorize a public request. Final test/source proof is `TEST_PROOF.json`.

Review invocation, run in the isolated source-only `review_snapshot` directory:

```sh
/Users/ayush/.codex/skills/autoreview/scripts/autoreview --mode local --no-web-search --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex --prompt-file review_prompt.md --output ../review_output_03.txt --json-output ../review_result_03.json
```

The installed binary SHA-256 was independently checked as `0d5ac7aae20c4eda6242428d5e218c55ba96d8763fda2a271088ff37104b9d28`. The engine stayed Codex; tools were on, web search was off. The reviewer states it performed read-only inspection and did not run tests/network requests. The snapshot contains only authored source, invented tests, protocol/gate, curated allowlist, test proof and source manifest. Its isolated empty Git repository exists solely for the local review helper; shared Git and all earlier freezes were untouched. No actual/private inputs, IDs, bodies, receipts, credentials or official raw source/header files entered this packet or review.

The immutable source manifest SHA-256 is `56a9c06af8691afc2b8af69b84bc92d194493a528801d32a17a3588e49dc0a11`; collector SHA-256 is `2338f51dd191540b2c6e12543937890b11155b048d34d704249e087c7fa0ff30`. Exact per-member pins are in `source_manifest.json` and `CURATED_PACKET_SHA256.txt`. The hash-list omits itself. Review outputs/snapshot machinery and fixture body artifacts are excluded from the curated public/reviewer allowlist.

The contract is transport-only: fixed 4-slot roster, at most four distinct unsigned single-attempt GETs, fixed deadlines/body-reader byte caps, exclusive outputs and conservative failure accounting. Deadline termination requests and receipt incompleteness are explicit under OS stalls. UTC daily-key basis, exact endpoint/selected-key mapping and actual acquisition authority remain separate unresolved prerequisites. A future parent must verify the curated pins, clean receipt, pushed freeze and independently authorized actual handoff before reading any actual inputs or invoking collection. This packet is neither that handoff nor an independent actual-result auditor; it earns no scientific/support/physical/model-improvement claim.
