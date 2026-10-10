# Header-only compatibility amendment, before any event queries or row analysis

10 October 2026. Original v1 protocol SHA256 remains `66ff3626ed7b4227c363a18e41261158e142bb92a1ca0bf68bf46136000dc14c`.

The first reviewed execution retrieved only the GitHub commit JSON, pinned README and pinned CSV: 3 requests, 665685 response-body bytes, 2.37 seconds. It stopped before iterating any rows because the README's EVENT_ID field is actually named PublicID in the CSV header. Header-only inspection established this; no eligibility/count/pick outcomes were inspected. Its all-zero summary is a failure placeholder, not evidence of absent events.

Accept exactly one identity column named EVENT_ID or PublicID (case-insensitive). Normalize PublicID to event_id internally, preserve original header/row values, and fail if both occur. No date, magnitude, deduplication, threshold, query-order or arrival policy changes.

Permit one narrow bootstrap continuation from this failed source-only run. Verify its pinned manifest, three raw files and request ledger against their original hashes, copy the exact source bytes locally, and reuse the same repository commit. Carry forward all three request attempts and all 665685 bytes; the 500-request/100-MiB ceilings remain combined ceilings. The original 30-minute window expired during the interruption; the separately authorized and frozen `RECOVERY_WINDOW_v1.md` grants one new 30-minute process window. This is an explicit budget amendment, not automatic deadline extension. Do not refetch main or substitute newer source files. Bootstrap supports only a source-schema failure with exactly these three successful requests; it is not a general retry/resume mechanism.

Real files remain solely in ignored local_runs. Code-only review receives this description, source/protocol hashes and invented fixtures, never real rows or QuakeML. The unchanged v1 population rules still precede all actual row analysis.
