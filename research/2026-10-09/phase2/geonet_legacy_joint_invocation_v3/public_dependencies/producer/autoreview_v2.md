autoreview findings: 2
[P2] [P2] Check colliding identities before filtering outside objects by namespace
projection.py:404
The outside-object scan excludes every node outside BED, and the native scan repeats this namespace filter. An extension such as `<ext:object publicID="smi:nz.org.geonet/p"/>` therefore bypasses identity validation even when a scoped pick has that ID: its local name is not CRITICAL, so reject_foreign also permits it. Projection then accepts the pick despite the cross-type collision. PROTOCOL_v2.md and specification.json require colliding publicID candidates anywhere inside the document root to invalidate correspondence. Scan all publicID-bearing outside nodes in both readers, retaining the existing behavior that ignores unrelated identities.

[P2] [P2] Normalize signed zero in canonical origin geometry
projection.py:96
Decimal.normalize() retains the sign of zero, so canonical_number("-0") returns "-0" while canonical_number("0") returns "0". compare() compares these canonical strings directly. Otherwise identical records with signed-zero latitude, longitude or depth consequently report a content mismatch and lose content-matched recovery counts, although their finite numeric geometry is equal. Canonicalize zero to a single representation before returning the geometry string; preserve the lexical arrival-weight guard separately.

overall: patch is incorrect (0.93)
The comment/PI boundary policy is implemented consistently, but the outside-scope identity scan misses colliding extension objects, and numeric geometry canonicalization distinguishes equivalent signed zeros. Both can produce incorrect compatibility results. Review used read-only source inspection; no tests or transforms were executed.
