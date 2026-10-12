# GEOFON immutable release follow-up: official mirror found, provenance still incomplete

12 October 2026. Documentary follow-up only; the earlier [v1 source audit](../earthquake_geofon_mw_donor_source_audit_v1/DECISION.md) is preserved byte-for-byte. Four queries, ten explicit opens and four clicks were bounded to official software/repository/license pages. No dataset file, metadata row, waveform, event-service query, author-code execution, installation, model fit, AWS action or Git mutation occurred.

**GEOFON remains a conditional candidate, not an accepted typed-Mw donor.** This pass identifies an official artifact location and a specific software-release commit target. It establishes neither an immutable GEOFON dataset edition nor agreement between hosted artifacts and a frozen converter/dependency chain. License, released schema and actual Mw support remain unverified; no training is earned.

## New primary evidence

The official SeisBench software repository gives a primary DESY/HIFIS storage root and distinguishes a backup repository. The primary-root open failed in this pass; no assertion about its contents follows from that failure. [Official repository](https://github.com/seisbench/seisbench).

GFZ's official repository landing page says its public models/datasets mirror the DESY primary repository. Following its dataset link and then GEOFON leads to an accessible directory listing. [GFZ repository landing](https://seisbench.gfz-potsdam.de/), [official GEOFON directory](https://seisbench.gfz-potsdam.de/mirror/datasets/geofon/).

The rendered GEOFON listing contains two file links: metadata.csv, displayed size **99M**, modified **2023-11-30 08:41**; waveforms.hdf5, **26G**, modified **2023-11-30 08:47**. These are rounded index values/timestamps, not byte lengths, hashes, a dataset version or reproducible acquisition receipts. Neither file was opened. No schema header or artifact contents were observed. The absence of further links in this particular rendered listing does not prove that documentation, hashes or release records are unavailable elsewhere. [Official GEOFON directory](https://seisbench.gfz-potsdam.de/mirror/datasets/geofon/).

The GFZ imprint states that datasets/models have individual varying licenses and points to the SeisBench software/GitHub. Its linked mirrored LICENSE repeats that distinction and separately assigns GPLv3 to SeisBench. Neither opened notice specifies GEOFON's dataset terms. Therefore software GPLv3 is not a verified GEOFON training/redistribution license. This is a documentation gap, not a finding that access or research use is prohibited. [GFZ imprint](https://seisbench.gfz-potsdam.de/imprint/), [linked repository LICENSE](https://seisbench.gfz-potsdam.de/mirror/LICENSE).

The official releases page associates tag **v0.12.0** with a link whose target contains commit **af0b7749362cecad345d32a22539ec07a1ff45ab**. It is a specific **software** reference, not a GEOFON artifact identifier. The commit-page click, tagged GEOFON/base source pages and corresponding full-commit raw-source opens failed in this pass. No fixed source bytes, dependency closure or converter-to-artifact agreement was established. Do not treat a failed source read as missing source or use the release label to assign provenance to 2023 hosted files. [Official releases page](https://github.com/seisbench/seisbench/releases).

The previously observed mutable converter and utility documentation rendered different revisions. The specific software pointer above does not resolve that disagreement or determine which transformation generated the hosted dataset. V1's counts/full-array mean/zero-fill/rotation cautions remain documented implementation observations; they are not rewritten as findings about verified released bytes. No repeated magnitude/converter survey was conducted here.

## Readiness and precise remaining work

| Requested documentary link | Established in this pass |
|---|---|
| Official artifact location | Yes: a GFZ mirror directory linked from the official repository landing. |
| Immutable GEOFON release/version | No verified dataset edition; directory timestamps and a software tag are insufficient. |
| Artifact manifest/integrity | Two documentary file links/sizes/times observed; exact byte hashes and a provider manifest remain unverified. |
| Released schema | No CSV header or HDF5 schema inspected. V1's converter interface is not silently equated with released columns. |
| Dataset-specific license | Repository says licenses vary; GEOFON-specific grant/terms unverified. |
| Matching converter/dependencies | Specific software commit target identified, fixed-source access failed; artifact provenance remains unverified. |
| Compatible Mw counts/causal physical inputs | Not inspected or established. No actual donor cohort or transfer-readiness claim. |

One precise next documentary step is to obtain an official GEOFON release/provenance record that joins the two artifact digests to an exact converter/dependency revision, input-provider versions and applicable dataset/network terms. An author-supplied manifest or provider clarification may supply it, but this packet does not authorize messaging anyone. If no immutable provider edition exists, a future separately authorized snapshot could establish locally reproducible artifact hashes; it would still require honest mutable-source provenance and dataset terms, rather than inventing a publisher release.

Only after that gate should a separately frozen metadata-only inspection determine actual column/type completeness, genuine moment-based Mw provenance, ordinary/high-Mw counts and sequence/test exclusions. Any waveform inspection would additionally need the existing accepted-network-P clock, complete grids, concurrent response/orientation/epochs and verified causal preprocessing. Keep unknowns and failures, and preserve all 1/3/5-second, bulk/worst-error and matched-control requirements. This follow-up changes no scientific denominator or acceptance criterion.

SOURCE_LEDGER.json records every explicit documentary access and prior authored packet pins. All online byte hashes remain null: web-rendered pages were inspected, while source/dataset byte files were not retained. The five-file public packet contains authored summaries and pins only; v1 remains unchanged.
