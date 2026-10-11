# Curated source-only allowlist

- `collector.py`
- `test_collector.py`
- `PROTOCOL_v1.md`
- `README.md`
- `ACTUAL_INVOCATION_GATE.md`
- `CURATED_ALLOWLIST.md`
- `TEST_PROOF.json`
- `source_manifest.json`
- `review_prompt.md`
- `review_result_final.json`
- `REVIEW_ACCOUNTING.md`
- `CURATED_PACKET_SHA256.txt`

Exclude all actual input/ID/roster/key/body/receipt/log artifacts, official raw sources/headers, credential/account files, fixture body files, interpreter caches and review snapshot `.git` machinery. Only invented source examples and aggregate test proof may be reviewed/published. Existing freezes are outside this packet and unchanged. The hash-list does not hash itself.
