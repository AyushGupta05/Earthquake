# Ready for source freeze; acquisition disabled

The completed GeoNet census is already promoted in parent milestonecf0641f. This new audit has no real StationXML/miniSEED request or response. Its final code-only review is clean,38 invented fixtures pass, and a separate analysis reproduced all5census input hashes,6selected event records,18station records and36frozen HTTPS archive requests exactly without importing audit/core.

The frozen six-event sample takes two in each nonoverlapping band: [5.5,6)years2003/2024;[6,7)years2003/2023;[7,infinity)years2003/2023. Eligible successful candidate populations are89/45/15. Each event uses only the three earliest NZ-associated stations, their observed location/channel prefix and its retrospective earliest accepted NZ P as T0. This is a deterministic historical availability audit; it does not replay an operational picker or packet delivery.

Private plan SHA256: `1adcce537f0b9bcff0fc69d74aab530c541c594252e620c020ce33dedff6c205`.
Canonical frozen request-list SHA256: `c56335ec43e2081962e83a923f2a1ce76463a3212a1377e30c92d87a39e48914`.
Dependency receipt SHA256: `14bfc6bc8088e578d0fdf2d76dad3e6fbec2a5e63e24ee4e91beac62e4f6ba21`.
Source/protocol/input bindings and parent receipt schema are in HANDOFF.json and source_freeze_manifest.json.

Workspace-local Python3.14.5/ObsPy1.5.1/NumPy2.5.4 and23pinned binary-wheel distributions are installed and verified. The runtime receipt retains exact interpreter provenance, package/wheel hashes, synthetic proof and cache caveat. No shared/global interpreter was modified. Package response transfer was exactly measured by the verified-wheel downloader and conservatively padded for preliminary resolver traffic; transfer plus disk remains below512MiB. Cache is now workspace-local.

Parent must copy only safe_to_promote_paths.json entries into the research repo, commit/push that source/protocol/runtime milestone, verify it, then create the separate parent acquisition receipt. The current source-freeze manifest intentionally says acquisition_authorized=false. It is not an execution receipt. Run from this original working directory after the parent receipt, using the exact local .venv; do not copy or relocate the virtual environment into Git.

The eventual one serial local CPU audit is bounded by1800seconds including validation,100attempts and128MiB combined response bodies, with36planned requests,4MiB StationXML/8MiB miniSEED per response and no retries/redirects/resume. A cap/timeout/child failure is incomplete, never negative feasibility. Preserve every station/deadline denominator and raw/native-warning logs locally. Publish aggregate/hash receipts only after independent raw-artifact replay.

Strict prefixes are [T0-5,T0+1/3/5), with absolute rational-index cropping, no samples at/after a deadline, no filtering/resampling/merging/filling or response inverse. Require coherent epoch-spanning ENZ/12Z metadata and aligned finite sample grids; mark clipping candidates only. Full finite transfer response is metadata consistency. All current code explicitly leaves physically_calibrated_prefix_verified and physically_unclipped_verified false. This preparation supports no model, novelty or published-benchmark superiority claim and no larger acquisition or AWS fitting.
