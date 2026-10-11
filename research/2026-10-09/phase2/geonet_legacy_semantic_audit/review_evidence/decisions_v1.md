# Verified first-review decisions

Review v1 exited 1 with three actionable findings in the source-only snapshot.

1. Mixed native/QML arrival weight vocabulary: verified using invented arrival fields. Accepted. Both directions now return unknown; seven regressions cover time/slowness/backazimuth vocabulary plus native used flags.
2. Exact native depth scaling exponent overflow: verified with invented finite Decimal 1e999999999999999999. Accepted. Unrepresentable scaled exponent now returns null geometry without rounding or losing available pick denominators.
3. Timestamp/station rejection ordering: verified wording ambiguity, but code already follows original_PUBLIC_PROTOCOL_v1.md: unique reference, weight, rejected-status, network/station, aware-time, dedup. Corrected README to that explicit order and added an invented both-invalid fixture. Rejected changing code precedence because the original frozen predicate requires station first; accepted fixing the documentation ambiguity. Inline source comment records the invariant.

Separately, the parent's public source-contract reminder supplied no producer code. Independently reproduced/fixed native requested raw ID substitution with colliding mapped IDs, and a trailing-space smi reference aliasing a separately amplitude-selected trimmed pick. Raw reference resolution now cannot choose that other object; it remains an unresolved lower bound and sets explicit mapping ambiguity that blocks guarded recovery. Invented cases also cover raw target present but pointing to a different projected object, and already accepted XX→NZ membership change yielding zero newly accepted recovery.

After all changes, tests_v7.txt records 235 invented tests, all passing. Raw actual inputs and producer implementation remain unread. Same Codex engine will review the updated complete snapshot; first clean ends edits/review.
