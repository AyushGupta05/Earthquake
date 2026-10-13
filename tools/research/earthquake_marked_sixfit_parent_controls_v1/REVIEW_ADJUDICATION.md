# Review v1: two accepted findings

Default code-only reviewer returned two P2 findings; both were confirmed in source and accepted.

1. Parent completion used the7200-second science deadline instead of7400 closure deadline. Child science remains capped7200 and source300/900; no new stage starts without its full science allocation. Parent transport finish is separately checked against the manager+20 bound, while durable cleanup/finalization can consume the fixed200-second reserve. Added positive within-reserve closure/no-new-science and late-transport regressions.
2. A zero transport exit plus active/unverifiable post-cgroup observation did not trigger a stop. Added one bounded stop attempt on the exact owned unit after such uncertainty, then one bounded inspection where closure budget remains. The original uncertainty still returns incomplete even if the second inspection verifies cleanup. Added owned-unit stop/reinspection regression. No retry or new scientific invocation.

No finding was rejected, no scientific source/protocol was changed, and no resource or actual input was accessed. Rerun focused tests and the same default code-only review before freeze.

# Review v2: one accepted finding

The bounded reconciliation added in v1 skipped the owned-unit stop callback when the closure budget had reached zero. Confirmed and accepted. The callback now receives timeout0 for a nonblocking best-effort owned-unit stop even after expiry; it receives no new wait budget, and cleanup remains unverified/incomplete. Inspection reconciliation still occurs only with remaining closure time. Added an expired-cleanup regression asserting the exact unit and zero timeout. No scientific changes, retries or actual resource actions.

# Review v3: one accepted finding

The outer runner timeout was granted fresh after a durable claim although the recorded dispatch timestamp preceded that claim. Confirmed with a sufficiently long authorization lease; retrospective rejection alone was insufficient. Timeout now subtracts the current monotonic time from the minimum of the original dispatch+manager+20 deadline and the fixed whole closure deadline. A10-second claim yields370, not380 seconds of remaining admission transport time. Added that explicit regression. Source and manager caps are unchanged; no new clock or permission is created.
