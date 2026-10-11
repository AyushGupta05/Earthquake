autoreview findings: 1
[P2] Include QML arrivals in the cross-type publicID guard
projection.py:373
The QML registry omits publicID-bearing arrivals. If the preferred origin's arrival has publicID="smi:nz.org.geonet/p" and its referenced pick has that same publicID, projection still returns status="ok" and accepts the pick. This violates the protocol's requirement that cross-type publicID collisions make the representation unknown, allowing an ambiguous representation to contribute clocks and recovery counts. Include publicID-bearing arrivals in collision checking, or apply an outside-object collision pass equivalent to the native reader.

overall: patch is incorrect (0.96)
Read-only inspection found a concrete gap in QML cross-type identity validation. A colliding arrival publicID bypasses the fail-closed guard and leaves the representation eligible for diagnostic counts. No tests or transforms were executed.
