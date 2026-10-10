# GeoNet metadata feasibility census

Protocol: `PROTOCOL_v1.md`, frozen before real CMT/event retrieval. Code uses only Python standard library. Source files and fixture tests are safe for Git/review. `local_runs/` contains real metadata and is excluded; never copy it into a reviewer or research repository.

Tests (no network):

```sh
cd work/geonet_tail_census
python3 -m unittest -v test_census.py
```

Real run is permitted only after the final code-only review is clean:

```sh
python3 census.py --output local_runs/census_20261010
```

The output must be a new resolved child of this helper's `local_runs` directory. No retries/resume/overwrite. All three source requests and every attempted event query consume the run's request/time/body-byte budgets. A capped run is explicitly incomplete. Review and fixture tests do not query real data.

The first run stopped before row iteration at the CSV's PublicID header. Its original deadline has expired. The narrow recovery described in `AMENDMENT_20261010_PUBLICID.md` and `RECOVERY_WINDOW_v1.md` reuses those exact three source files under one explicitly authorized fresh window, retaining combined request/byte totals. After clean review and freezing the recovery execution manifest, use:

```sh
python3 census.py --output local_runs/recovery_20261010 \
  --bootstrap local_runs/census_20261010 \
  --recovery-plan approved_recovery_execution_manifest.json
```

The failed first run's zero counts are placeholders, never a population conclusion.

Raw bytes live under `raw/`; `requests.json` records URL/body hash/byte/status/UTC for each attempted request. `rows.json`, `groups.json`, `query_order.json` and `outcomes.json` are local real metadata ledgers. `summary.json` contains aggregates; `manifest.json` hashes every completed file and pins source/protocol/runtime. The public repository SHA is obtained once, and both CMT sources use that immutable SHA.

Only a curated findings memo, aggregate summary, independently checked hashes and a small handoff manifest should be published. Review context explicitly confines inspection to the isolated snapshot's code, protocol and invented fixtures. No source rows, inventory or credentials are sent to the reviewer.

The statistical object is unique catalogued event identity with measured CMT Mw, not independent tectonic sequence count. The time object is a retrospective associated P-pick UTC time, not waveform availability, packet latency or causal detection. No predictions or training are involved.
