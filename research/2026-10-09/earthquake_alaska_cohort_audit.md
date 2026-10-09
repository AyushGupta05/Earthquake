# Alaska archive and published cohort reconciliation — 2026-10-09

**Unresolved: the release has 781 named replay pairs, mapping to 780 current ComCat events; the paper reports 530.** No membership manifest or exact exclusion rule was found in the public archive metadata, article, or successfully retrieved supplement. Nothing has been dropped to make counts agree. No waveform bodies were read, no models scored, and the parent-owned full archive download was untouched.

## Primary-source boundary

The [paper, DOI 10.1785/0120260139](https://doi.org/10.1785/0120260139), describes 530 M4.5–8.2 earthquakes during January 2010–February 2025 across Southeast Alaska, inland Alaska and the Peninsula region, including selected distant offshore events. It reports eight M≥7 events, mean depth 57 km, 63 deeper than 100 km, and 345 matched/185 missed replays. Its matching requirements (100 km/30 s plus alert checks) classify outcomes; they are not archive exclusions. No numerical geographic polygon or 530-ID list appears in its text. The separately described 346-event West Coast comparison is not a stated component of this release.

The [publisher supplement](https://gsw.silverchair-cdn.com/gsw/Content_public/Journal/bssa/PAP/10.1785_0120260139/2/bssa-2026139_supplement.docx) was retrieved through its visible publisher link. Table S01 contains location-error summaries inside/outside an Aleutian polygon, not event IDs. Four figures cover location errors, a station-magnitude example and a quality filter. Neither the extracted text nor its table supplies cohort membership. The polygon separates a results analysis; it is not an exclusion rule. No contact with authors was made.

The [Zenodo release](https://zenodo.org/records/19897535) is one ZIP with no additional README/catalog/manifest. Its metadata supplies no description or selection rule. Existing parent ZIP-index/CRC audit confirms 781 `.dat` and 781 `_replay.seed` names with equal normalized-ID sets. Channel files carry station coordinates/gains/units, not event selection flags. They cannot resolve membership by themselves.

## Identity reconciliation, independent computation

A bounded [USGS FDSN metadata query](https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2010-01-01&endtime=2025-03-01&minmagnitude=4.5&minlatitude=48&maxlatitude=73&minlongitude=-190&maxlongitude=-125&orderby=time-asc&limit=20000) returned 2,723 features. Intersecting each feature ID and comma-separated `properties.ids` aliases with the archive IDs maps **all 781 IDs**, with no missing or multiply assigned aliases, to **780 distinct current ComCat features**. The only duplicate pair is `iscgem614401514` and `us1000hyge`, both current preferred event `us1000hyge`, M5.2, 2018-11-30 18:00:06.570 UTC. This is a catalog-identity duplicate; waveform equivalence has not been examined. Archive ID `ak0251no79q2` maps to current preferred `ak0251no79w4`.

Thus catalog aliases explain **one**, not 251, extra named files. If the paper's 530 are a subset of these current events, 250 distinct events remain unexplained; that subset relationship itself has not been verified. Catalog revisions may alter historical parameters/aliases. This current snapshot is an audit aid, not a reconstruction of the authors' February 2026 catalog snapshot. USGS documents [GeoJSON fields](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php) and the [query service](https://earthquake.usgs.gov/fdsnws/event/1/).

## Exploratory distributions, no fitted cohort boundary

Counts below count unique current ComCat events (780). The duplicate adds one M5.2, 2018, 60–65°N and 150–145°W archive row.

| Magnitude | Count |
|---|---:|
| 4.5–4.9 | 527 |
| 5.0–5.9 | 229 |
| 6.0–6.9 | 16 |
| ≥7.0 | 8 |

All are currently M≥4.5. Origin times span 2010-01-21 through 2025-02-05; 779 precede 2025-02-01, all 780 precede 2025-03-01. Year counts 2010–2025: **43,48,31,41,36,25,35,44,113,52,116,63,45,55,31,2**. This stated magnitude/date envelope therefore does not explain the discrepancy.

| Longitude interval | Count |
|---|---:|
| [−180,−165) | 22 |
| [−165,−160) | 145 |
| [−160,−155) | 214 |
| [−155,−150) | 191 |
| [−150,−145) | 134 |
| [−145,−140) | 18 |
| [−140,−135) | 42 |
| [−135,−130) | 14 |

Longitude range is −167.808 to −130.9016; latitude is 53.6458 to 66.4029. Latitude-bin counts [50,55),[55,60),[60,65),[65,70) are **237,356,158,29**. No archive events lie west of 170°W; 22 lie west of 165°W. These illustrative fixed bins do **not** define western-Alaska exclusions: the paper does not give a numerical region boundary from which an exclusion count can be recovered. Do not optimize a longitude/latitude cut to yield 530.

Current depths span 0.6–212.44 km, with mean 40.580 km and 77 events deeper than 100 km. This differs from the published cohort summary, further supporting an unresolved cohort/snapshot difference without identifying its cause. No new data-quality exclusion has been inferred from this comparison.

## Saved provenance and required next step

- `archive_index.json`, `metadata_audit.json`, `zenodo_record.json`, `sparse_index.zip`: parent inputs, unchanged. No `.seed` sparse holes read.
- `cohort_comcat_region.geojson`: 2,076,202 bytes; SHA256 `7dfede4f3f12313d6073d044f1861668d3bd30de9e5e628e5872d6b6e24be214`.
- `cohort_comcat_region_provenance.json`: full query URL/parameters and UTC retrieval time.
- `cohort_alias_initial.json`: all 780 groups and their 781 archive IDs, current magnitude/time/coordinates, zero unmatched IDs.
- `cohort_distribution_audit.json`: both unique-event and archive-row distributions.
- `bssa-2026139_supplement.docx`, extracted `.txt`, `supplement_provenance.json`: exact supplement URL/hash/size.

To reproduce the paper cohort, obtain an explicit 530-event manifest (including preferred/alternate IDs and catalog version), the actual selection script/configuration, or author clarification. A later study could instead preregister its **own explicitly named released-archive cohort**, resolve the duplicate transparently and freeze a catalog snapshot, but cannot call that the published 530-event benchmark. Waveform integrity/availability, picks, causality and evaluation eligibility remain separate audits.
