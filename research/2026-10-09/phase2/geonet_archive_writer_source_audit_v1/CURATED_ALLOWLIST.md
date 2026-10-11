# Curated packet allowlist

Only the following exact relative files are eligible for public documentation handoff or later source-only review/publication:

- `AUDIT.md`
- `PROSPECTIVE_FOUR_SLOT.md`
- `CONFIGURED_TEMPLATE.json`
- `SOURCE_PINS.json`
- `native_request_ledger.json`
- `REQUEST_SCOPE_LEDGER.md`
- `CURATED_ALLOWLIST.md`
- `CURATED_PACKET_SHA256.txt`

Every other file, including the entire `inert_public_sources/` directory, is excluded. External raw sources, HTML, source/API response bodies, HTTP headers, actual inputs/keys/IDs/rosters, private receipts/body files, credentials and raw official source text must not be copied into review/publication from this packet.

`CURATED_PACKET_SHA256.txt` hashes the seven other allowlisted members, not itself. The packet contains no actual-data or acquisition authorization. Existing source/code/test/review freezes remain unchanged.
