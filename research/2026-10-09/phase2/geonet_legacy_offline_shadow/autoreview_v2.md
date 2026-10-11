autoreview findings: 2
[P2] P2: Check scoped IDs against unselected objects for cross-type collisions
projection.py:447
The native registry excludes unreferenced origins and unselected amplitudes. Adding an unreferenced sibling origin with publicID="p" to the native fixture therefore leaves the referenced pick publicID="p" accepted and the representation marked "ok". This violates the protocol requirement that cross-type publicID collisions remain unknown. Check objects whose IDs collide with scoped identities even when those objects are excluded from projection; their inclusion in identity validation need not broaden the projected scope.

[P2] P2: Deduplicate stations using a network/station tuple
projection.py:499
Joining the two codes with a dot is not an injective station key. Accepted picks with (network, station) equal to ("NZ.A", "B") and ("NZ", "A.B") both become "NZ.A.B", so all_network.station_count and its horizon counts undercount distinct stations. The frozen acceptance contract requires only nonempty codes, and this reader does not prohibit dots. Use (pick["network"], pick["station"]) as the dictionary key.

overall: patch is incorrect (0.96)
Static inspection identified an incomplete native cross-type identity guard and a collision-prone station deduplication key. Both can produce known results that violate the frozen protocol. No tests, transforms, network requests, or file modifications were performed.
