# Verified third-review decisions

Review v3 exited 1 with two actionable source-only findings. Both were accepted after checking the independent code and adding invented regressions.

1. Duplicate-pick exemption was based on same local type among descendants rather than actual pick collection membership. Restrict exemption to nodes that all belong to the direct event-scoped picks collection used for resolution. Nested same-ID picks in both representations now remain unknown; actual direct duplicate picks continue to be unresolved lower bounds.
2. Identity index began at EventParameters rather than the document root, despite the documented whole-document guard. Index root-level sibling publicIDs too, without adding them to event scope. Native candidate collision and QML raw collision are unknown; a distinct outside sibling still does not add a pick to the denominator.

After fixes, tests_v11.txt records 254 invented tests, all passing. Actual inputs and producer implementation remain unread. Same Codex engine reviews the updated complete snapshot; first clean ends edits/review.
