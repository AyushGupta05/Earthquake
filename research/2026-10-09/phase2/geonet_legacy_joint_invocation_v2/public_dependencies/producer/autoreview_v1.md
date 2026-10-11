autoreview findings: 3
[P2] [P2] Apply source whitespace stripping to native creation candidates
projection.py:212
Native creationInfo candidates retain whitespace-only text unchanged. For example, <author> </author> produces candidate author=" ", whereas the pinned stylesheet's xsl:strip-space removes that text node and produces an empty author. Comparing the corresponding QML and native records therefore reports a revision conflict and suppresses content-matched recovery despite equivalent source-derived metadata. Preserve the original text in raw_creation, but account for source whitespace stripping in candidate fields, including applicable xml:space handling, or fail closed when equivalence cannot be established.

[P2] [P2] Check colliding outside identities across the document root
projection.py:394
The outside-object scan starts at eventParameters, so it misses publicID-bearing objects elsewhere inside the document root. Adding a BED pick beside eventParameters with the same publicID as the selected pick leaves the representation ok and the pick uniquely accepted, despite the protocol requiring an outside same-type duplicate to make it unknown. The native scan has the same limitation at line 487. Inspect the whole root for colliding outside identities while retaining the existing projection scope.

[P2] [P2] Validate use flags on all referenced-origin arrivals
projection.py:468
Arrivals from every referenced origin participate in pick selection, but projected_weight validates flags only for the preferred origin later in the function. A second referenced origin containing timeUsed="yes", or duplicate timeUsed children, therefore leaves the native representation ok even though these scoped fields violate the frozen fail-closed policy. This also allows that representation to lend its profile to QML. Validate flags and weight singletons for every referenced-origin arrival, while retaining only preferred-origin arrivals in the comparison output.

overall: patch is incorrect (0.95)
The comment/PI boundary rejection implements the intended v2 policy, but source whitespace handling and two scoped-validation gaps violate the supplied contracts. Review used read-only inspection; no tests, transforms, or network requests were executed.
