autoreview findings: 3
[P2] Require exact raw native event identity before ID conversion
projection.py:400
The native event check compares mapped IDs, although that mapping is not injective. For example, supplied event_id "a:b" accepts a native event with publicID "a b" because both become "smi:nz.org.geonet/a_b". Neither collision registry includes the supplied raw event_id, so the substituted event returns status "ok" and can establish the QML profile binding. Compare native publicID against the supplied raw identity before conversion, as required by the protocol's substituted-ID policy.

[P2] Resolve raw arrival references before stripping candidate IDs
projection.py:467
Stripping the mapped arrival ID can turn a dangling raw reference into an accepted pick. Consider an arrival referencing "smi:invented/p " with no exact target, while an amplitude selects the existing pick "smi:invented/p". Selection and collision checks preserve these as distinct IDs, but this strip makes the arrival resolve to the amplitude-selected pick. analyse() then accepts it and includes it in clocks, contrary to the rule that dangling targets never establish correspondence. Require a unique exact raw pick target before using its candidate ID for acceptance.

[P2] Calculate newly accepted NZ references against left-side NZ acceptance
comparison.py:87
The NZ recovery counter intersects with newly_resolved, which has already removed every left-side accepted pick regardless of network. If the same left-qualified pick is accepted with network "XX" on the left and repaired to "NZ" on the right, newly accepted across networks correctly remains zero, but newly_accepted_NZ_reference_count incorrectly remains zero too. The protocol declares these as separate recovery counts. Compute the NZ gain from right-side NZ acceptance minus left-side NZ acceptance, restricted to left-qualified IDs.

overall: patch is incorrect (0.98)
Native identity and reference guards can accept substituted events or dangling references, and NZ recovery accounting misses network repairs. These violate the frozen diagnostic contracts. Review used read-only source inspection; tests were not run.
