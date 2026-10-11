# Verified second-review decisions

Review v2 exited 1 with two actionable source-only findings. Both were accepted after reading the independent code path and constructing invented regressions.

1. Raw/projected reference mismatch guard depended on uniqueness. Fixed by comparing literal target identity multisets and checking projected reference stripping separately, regardless of object multiplicity. A duplicate padded smi target cannot become a guarded trimmed-ID recovery; ordinary duplicate pick IDs remain unresolved lower bounds and can legitimately gain uniqueness later. Added duplicate/absent target, ordinary duplicate repair and guard tests.
2. Secondary QML origin arrivals skipped scalar/vocabulary validation. Every event-scoped origin now validates arrival fields in both representations. Preferred-origin arrivals alone still supply denominators/signatures. Added mixed vocabulary, duplicate phase, non-scalar weight and valid-secondary unchanged-denominator tests.

The parent's separate public relation-contract reminder supplied no producer code: outside-scope objects sharing raw/candidate identity with selected objects must keep ambiguity explicit. Added document-wide publicID collision checks against selected objects without expanding scope, covering outside pick/origin and wrong-type amplitude/magnitude collisions. Native and QML scoped magnitude wrong-type reuse is also unknown. Ordinary selected duplicate pick IDs retain the existing lower-bound behavior.

After all changes, tests_v10.txt records 249 invented tests, all passing. Actual inputs and producer implementation remain unread. Same Codex engine reviews the updated complete snapshot; first clean ends edits/review.
