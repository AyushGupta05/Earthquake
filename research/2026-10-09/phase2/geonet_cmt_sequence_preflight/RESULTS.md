# Full cached CMT frame: sequence planning preflight

**The full horizontal/time screen is computable offline, but its longer sensitivity graph percolates and fails the 200-event TEST planning floor.** This is an exploratory graph of the pinned CMT epicentres/minute anchors. It is not a definitive preferred-origin split, verified physical sequence partition, or available-prefix benchmark. The frozen 346-event metadata collection is unchanged.

The original 3,727 row dictionaries match the pinned CSV exactly. All 3,437 eligible event groups have one source row, one literal date and finite in-range four-decimal epicentre latitude/longitude. There are no unknown vertices or incompatible multirow cases; all 286 excluded groups remain accounted. Exact compatibility rules for hypothetical multirows were checked with invented fixtures. GeoNet's pinned README calls these horizontal fields epicentres; CD is centroid depth and was not used. The project's UTC-minute convention is retained, while README's date description alone does not establish timezone or exact origin seconds.

Every eligible pair within the time windows was considered: 83,789 pairs within 30 days and 189,882 within 90 days. Primary edges require <=30 days and <=100 km; sensitivity edges require <=90 days and <=150 km. Spherical distances wrap longitude correctly. Entire cross-cut components and a fixed closed ±30-day guard around both 2015/2018 cuts are quarantined in both scenarios. No event falls exactly on a guard boundary. There is no reallocation, replacement or forecast-based choice.

| Graph | Edges | Components | Largest component | Largest component span |
|---|---:|---:|---:|---:|
| 30 days / 100 km | 42,182 | 1,008 | 357 events | 400 full days |
| 90 days / 150 km | 76,249 | 148 | 3,080 events | 7,192 full days, 2005–2024 |

The primary graph has one component crossing a cut: 43 events across 2018, with no Mw>=5.5 member. The sensitivity graph has one component crossing both cuts: its 3,080-event giant component. Transitivity allows these spans to exceed the individual edge thresholds; the giant component is not evidence that all its events form one physical aftershock sequence.

| Calendar partition | Original events | Guard only: events remaining | Primary graph + guard: remaining | Sensitivity + fixed guard: remaining |
|---|---:|---:|---:|---:|
| TRAIN 2003–2014 | 1,732 | 1,720 | 1,720 | 236 |
| DEV 2015–2017 | 566 | 544 | 534 | 32 |
| TEST 2018–2024 | 1,139 | 1,127 | 1,107 | 89 |

Primary component/guard overlap is 13 events, yielding 76 quarantined in total. All 46 guard events lie in the sensitivity giant component, so sensitivity quarantines exactly 3,080 and leaves 357 total events. Counts retain their original calendar membership.

| Scenario | Partition | Remaining Mw>=5.5 | Mw>=6 | Mw>=7 |
|---|---|---:|---:|---:|
| Primary + guard | TRAIN | 69 | 29 | 8 |
| Primary + guard | DEV | 30 | 12 | 2 |
| Primary + guard | TEST | 49 | 19 | 5 |
| Sensitivity + guard | TRAIN | 27 | 13 | 6 |
| Sensitivity + guard | DEV | 4 | 3 | 0 |
| Sensitivity + guard | TEST | 30 | 15 | 4 |

These are optimistic **pre-waveform** ceilings. Under this exact CMT sensitivity/quarantine candidate, a TEST with >=200 events is impossible even if every remaining event has usable data. Its tail ceilings exactly equal the 30 Mw>=5.5 / 15 Mw>=6 planning floors, leaving no attrition margin. The primary screen preserves those floors before waveform attrition, but this does not justify selecting it because it gives larger counts or assuming it proves sequence isolation. Retain the sensitivity failure when defining any later benchmark. Preferred-origin revisions could alter connectivity, so this is not an impossibility proof for every future origin-based design.

The graph computations were independently checked using a separate unit-vector chord-distance adjacency/BFS calculation rather than haversine/union-find. Both edge counts, component counts/size histograms and all post-quarantine calendar/tail tables match. Eight considered pairs are within 0.02 km of each distance threshold; they retain the exact inclusive rule, with no tolerance-based reclassification. The source coordinate decimals do not establish physical location uncertainty.

## Cached horizontal-source comparison

All 149 preferred-origin horizontal locations were independently linked/validated from their original checksum-pinned XML, and compared without replacing CMT graph vertices. Distances are descriptive provenance differences, not proof of wrong event identity.

| CMT versus preferred horizontal distance | Mw>=5.5 (149) | Mw>=6 (60) | Mw>=7 (15) |
|---|---:|---:|---:|
| <=0.1 km | 60 | 33 | 9 |
| >0.1 to 1 km | 13 | 2 | 0 |
| >1 to 5 km | 29 | 11 | 3 |
| >5 to 10 km | 13 | 1 | 0 |
| >10 to 25 km | 17 | 7 | 2 |
| >25 to 50 km | 9 | 3 | 1 |
| >50 to 100 km | 6 | 2 | 0 |
| >100 km | 2 | 1 | 0 |

Both literal external_wphase cases are within 5 km (one <=0.1 km, one >1–5 km); neither explains the >100-km differences. The two distance formulations independently match all bins. These differences prevent treating CMT positions as interchangeable with preferred-origin geometry, even though the full CMT frame is sufficient for this bounded preliminary graph.

[graph_aggregate.json](graph_aggregate.json), [cached149_coordinate_comparison.json](cached149_coordinate_comparison.json), [schema_audit.json](schema_audit.json) and [verification.json](verification.json) contain aggregate evidence; [input_provenance.json](input_provenance.json) pins the exact sources and [PROTOCOL.md](PROTOCOL.md) preserves the pre-calculation rules. No IDs, coordinate rows, timestamps, picks, URLs or graph rosters are published. No additional 2,942 QuakeML queries were needed for this horizontal preflight; it does not replace any later preferred-origin, response, waveform or availability audit. No acquisition, AWS, Git, model input, forecast, fit or live collection read occurred.
