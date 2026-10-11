# Independent eight-slot archive transport auditor V3

This source-only pure auditor starts from frozen independent V2 and implements the normative public collector V4 contract. It reads no collector implementation or actual/private artifacts. Its API, custody requirements, limits and uncertainty scope are in PROTOCOL.md.

Eight fixed E/N roles, exact new study/proposal identity, 64 MiB per body and 512 MiB total replace the old four-slot envelope. All other chronology, finalization, pin, exact/nonexact accounting, framing and false semantic/physical claims remain conservative. Complete receipts may qualify individual transport slots; a failed slot never qualifies, and invalid or incomplete replay qualifies none. Full filesystem inventory and actual selection/clock/authorization verification remain parent responsibilities.

The 45 previous invented test methods are adapted for eight slots without discarding their purposes. Eight additional methods cover every role suffix, exact production identity, incompatible old four-slot plans, missing/out-of-order eighth members, eighth duplicate deduplication, exact 512 MiB aggregate/over-cap, synthetic E/N pairs and per-slot partial failures. All tests use invented in-memory bytes.

Focused tests and default no-web Codex autoreview run on an isolated source-only snapshot, until first clean. Reviewer access excludes raw external sources, actual/private inputs, collector implementation, credentials and nested reviews. Prior packets remain unchanged. Source review does not grant actual acquisition/replay authority. Publication uses only PUBLIC_ALLOWLIST.txt and a closed hash manifest; review_snapshot and Git internals are excluded.
