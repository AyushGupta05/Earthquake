# STEAD local-distance cache (fourth catalogue)

Built 30 Oct 2026 by `tailrisk/stead_prep.py` on `instancebaseline`; cache at
**`/mnt/scratch/stead/`** (3.5 GB). Nothing has been trained on it yet.

**`/mnt/scratch` is ephemeral and is lost when the instance stops.** To rebuild (about 15 min,
CPU and network only, peak RSS about 1.5 GB):

```bash
cd ~/Earthquake/tailrisk && TAILWORK_DIR=/mnt/scratch/stead nice ../.venv/bin/python stead_prep.py --workers 6
```

## Environment for a training or evaluation run

```bash
TAILWORK_DIR=/mnt/scratch/stead TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0 TAILWORK_THR=5,5.5,6
```

- `TAILWORK_MAXMAG=9.5`: the largest label is 7.9. 8.5 would be enough, but 9.5 matches Chile and GEOFON.
- `TAILWORK_MAXLOGR=3.0`: the default; hypocentral distance is at most 447 km, so bins 0–22 of 26 are used.
- `TAILWORK_THR=5,5.5,6`: tail thresholds for `geofon_eval.py`. They cover 718, 191 and 63 events.
  To also report M≥4 (7,621 events), use `4,5,6`.
- CV only: `split` is 0 for every row, as in Chile and GEOFON, so use `--mode cv`.
  SeisBench's own STEAD split is per trace and 89 k events cross it. It is kept as `split_seisbench`
  for reference only.

## Why STEAD

The feasibility thresholds were at least 30 M≥5 events and physical units for most traces.
STEAD clears both by a wide margin, so the other SeisBench catalogues were not compared in detail:

| | raw STEAD | in the cache |
|---|---|---|
| earthquake traces (all have a P pick and a magnitude) | 1,030,231 | **996,894** records |
| distinct events (source_id) | 441,705 | **435,893** (after merging duplicates) |
| events M≥4 / M≥5 / M≥6 / M≥7 | 8,296 / 773 / 69 / 3 | **7,621 / 718 / 63 / 2** |
| records M≥4 / M≥5 / M≥6 | 23,978 / 2,038 / 146 | 19,199 / 1,676 / 121 |
| stations / networks | 2,637 / 140 | 2,579 / 136 |

For comparison: INSTANCE has 31 M≥5 events and Chile has 12 M≥6. STEAD covers 1988–2018 and
epicentral distances up to 346 km (median 38 km). Hypocentral distance runs from 2.5 to 447 km,
and depth reaches 342 km.

Where the M≥5 events are:

| region | M≥5 | M≥6 |
|---|---|---|
| Alaska and Aleutians | 233 | 27 |
| Chile and Argentina | 158 | 8 |
| Greece and Aegean | 85 | 8 |
| New Zealand | 51 | 6 |
| California and Nevada | 50 | 3 |
| Central America | 25 | 3 |
| Cascadia | 17 | 3 |
| other | 99 | 5 |

The M≥5 events fall into 456 Gardner–Knopoff clusters, and the M≥6 events into 51.

## Source and access

- SeisBench mirror: `https://seisbench.gfz-potsdam.de/mirror/datasets/stead/`
  (`waveforms.hdf5` is 91.1 GB; `metadata.csv` is 403 MB).
- HDF5 attributes: `component_order=ZNE`, 100 Hz, `unit=counts`, `instrument_response=not restituted`.
- The STEAD authors already detrended the traces and band-passed them at 1–45 Hz. I checked this
  on raw traces: there is no energy above 46 Hz.
- The bucket datasets are contiguous, uncompressed float32 arrays of shape (1024, 3, 6000).
  The script reads each dataset's byte offset once (cached in `bucket_offsets.json`) and then
  fetches the needed rows with plain HTTP range requests on 6 threads. There is no 91 GB
  download; the rate was about 96 buckets per minute, about 10.5 min for all 1,007 buckets.
- Station metadata comes from the FDSN channel level via IRIS fedcatalog, which routes each
  request to the data centre that holds the network (EarthScope, NOA, RESIF, GeoNet and others).
  It is fetched as text, one request per network for the STEAD stations (138 networks,
  38,189 channel epochs), cached in `/mnt/scratch/stead/inventory/<NET>.txt`.
  The `Scale` column is the channel's InstrumentSensitivity, the same value StationXML gives,
  without parsing a large XML inventory.

## Physical units

Each trace is matched to the channel epochs of its network, station and family that contain the
trace start time. Only m/s units are accepted, with |Scale| > 0.

STEAD does not record the location code. When a station has several location codes for one
family, the trace is kept only if their vertical sensitivities agree within 5%.

Coverage of the 1,028,387 velocity-family traces (HH, BH, EH, SH):

| status | traces | of which M≥5 |
|---|---|---|
| ok | **1,018,111 (99.0%)** | 1,955 of 2,020 |
| ambiguous location (gains differ) | 4,474 | 29 |
| not in m/s | 4,051 | 30 |
| no epoch covering the trace time | 767 | 2 |
| no inventory | 577 | 4 |
| station more than 5 km from the inventory position | 375 | 0 |
| no vertical channel | 32 | 0 |

- Only 18 records lack a horizontal sensitivity. They use the vertical gain and are marked
  `usable=False` for that component.
- 1,844 traces from other families were left out (EL, HL, BL, LH).

## Cache format (same layout as the Chile and GEOFON caches)

### Waveforms

- `wave16.npy` is float16 of shape (996894, 3, 500); `scale.npy` is float32 of shape (996894,).
- Each window starts at the catalogue P pick and runs 500 samples (5 s) at 100 Hz.
  There are no samples before P. This matches GEOFON and Chile, where `p:p+500` is stored, and
  INSTANCE, where the 1 s and 3 s inputs are the first 100 and 300 samples.
- Component order is **E, N, Z**: the file's ZNE is reordered.
- `wave16 × scale` gives counts, and **`wave16 × scale × phys_factor[:, c]` gives ground velocity
  in m/s**, with `phys_factor = 1 / sensitivity`. This is the INSTANCE convention, so the cache
  could be recalibrated without downloading again.
- Checked against direct HDF5 reads: maximum relative error 2.4e-4, which is float16 rounding.

### `meta.npz` fields read by the trainer

`split`, `event`, `station`, `stations` (2,579 NET.STA), `family`, `families` (BH, EH, HH, SH),
`mag`, `mag_type`, `fold`, `cluster`, `static`, `static_names`, `gains` (counts per m/s, E N Z),
`usable`, `phys_factor`, `sta_lat`, `sta_lon`, `hyp_km`, `epi_km`, `depth_km`.

`static` holds 8 columns, all station metadata known before the event:
`log10_sensitivity`, `family_HH`, `family_BH`, `family_EH`, `family_SH`, `log10_native_rate`,
`elevation_km` and `sensor_depth_km`. `GPUData` then appends station latitude and longitude.

### `meta.npz` fields for analysis only

- `baz`, `origin_t`, `trace_name` (SeisBench bucket and row) and `source_id`.
- `p_sample` is 0. `p_sample_source` is the P sample in the 60 s STEAD trace. `s_sample` is the
  S−P gap in samples, so it is the S position in the cached window.
- `p_after_network_s` is the P time relative to the event's first P among *STEAD records* only,
  not a full network. `fusion_timeline.py --times measured` can use it.
- `p_manual` (74% of picks are manual), `rate` (100 for all), `native_rate`, `source_mag`,
  `source_mag_type` and `split_seisbench`.

### Other files

`events.csv` (one row per event with its cluster and fold), `folds.json` (summary and selection
counts), `gain_qc.npz` (see below), plus `selected.pkl`, `inventory/` and `bucket_offsets.json`,
which are intermediates for rebuilds.

## Labels and duplicates

- **One magnitude per event.** Rows of one event in STEAD can carry different magnitudes from
  different networks (8,480 source_ids). The label is the median over the event's rows of the
  preferred type: Mw* > ML > Md > mbLg > mb > other.
  - `mag_type` uses conventional spelling (`ML`, `Md`, `mb`, `Mw`, `Mww`, …), so `train.py`'s
    `startswith('Mw')` test works. Mw-type records are 0.8% of all records.
  - M≥5 events by type: Mw* 525, **mb 151**, ML 37, Ms 3, Md 1, mpva 1.
  - M≥6 events by type: Mw* 56, mb 3, ML 3, Ms 1.
- **source_id is not unique.** 77 ids are reused for different earthquakes, so events are keyed
  by source_id plus origin time.
- **Duplicate catalogue entries are merged.** Different ids within 5 s and 50 km are treated as
  one earthquake: 438,075 entries become 435,916 events. For example, the 2002 Denali M7.9
  appears under two ids. The cache's 435,893 events are what remains after 38 records with an
  all-zero vertical were dropped.
- **Duplicate recordings are dropped.** 21,179 traces are copies of one recording: same event,
  station and family, absolute P within 1 s, but a window shifted by 1–5 s.

## Clusters and folds

Gardner–Knopoff mainshock windows come from `prep_data.sequence_clusters`, visited largest-first,
with a foreshock fraction of 0.25. That gives 145,128 clusters. `prep_data.assign_folds` then
balances M≥5 events, M≥4 events and records over 5 folds:

| fold | events | records | M≥4 events | M≥5 events | M≥6 events | max M |
|---|---|---|---|---|---|---|
| 0 | 89,370 | 198,224 | 1,528 | 144 | 9 | 7.7 |
| 1 | 88,136 | 198,879 | 1,523 | 144 | 17 | 6.8 |
| 2 | 92,330 | 199,933 | 1,527 | 143 | 7 | 7.9 |
| 3 | 78,075 | 199,933 | 1,528 | 143 | 15 | 6.9 |
| 4 | 87,982 | 199,925 | 1,515 | 144 | 15 | 6.8 |

M≥6 was not a balancing target, so it ranges from 7 to 17 per fold. Evaluation pools
out-of-fold predictions, so all 63 events count. The largest cluster holds 6,102 events and
12,485 records (max M5.6).

## Sanity checks (`/mnt/scratch/stead/check.log`)

### Counts and integrity

- No field read by the trainer is non-finite. `depth_km` is NaN for 46 rows; `hyp_km` uses
  10 km for those.
- Each event has one magnitude and each cluster one fold.
- `GPUData` loads the cache. 1, 3 and 5 s prefixes, amplitude, invariants and normalized static
  inputs are all finite (checked on a 200 k-row subset on CPU).

### P timing vs distance

- **Absolute P travel time** (catalogue origin to P pick) gives a median `hyp/tt` of 5.2, 5.8,
  6.0, 6.8 and 7.2 km/s in the 0–25, 25–50, 50–100, 100–200 and 200–500 km bins. Only 0.8% of
  records fall outside 3–12 km/s, and no pick precedes its origin.
- **Within an event**, P delay against extra hypocentral distance has a slope of 0.145 s/km,
  an apparent velocity of 6.9 km/s, over 406 k pairs.

### Log amplitude vs magnitude

The fit is log10 RMS(3 s) = a·M + b·log10 R + c. Columns 3–4 use physical units; the last two use
raw counts:

| subset | n | a | resid sd | corr(M, dist-corrected A) | resid sd (counts) | corr (counts) |
|---|---|---|---|---|---|---|
| all | 155 k | 0.89 | **0.467** | **0.903** | 0.562 | 0.855 |
| ML | 108 k | 0.92 | 0.433 | 0.881 | 0.538 | 0.802 |
| Md | 35 k | 0.87 | 0.477 | 0.800 | 0.545 | 0.740 |
| mb | 7.5 k | 0.89 | 0.607 | 0.727 | 0.679 | 0.671 |
| Mw | 2.8 k | 0.67 | 0.588 | 0.650 | 0.644 | 0.628 |
| family EH | 38 k | 0.85 | 0.455 | **0.833** | 0.639 | 0.524 |

- Physical units cut the scatter by about 0.1 dex. For EH short-period sensors they are what makes
  amplitude informative at all, which shows the sensitivities are right overall.
- **Borehole offset.** Borehole sensors sit about 0.37–0.40 dex low: PB borehole EH −0.40,
  borehole HH −0.37, against +0.09 to +0.19 for surface EH, HH and BH. That is the missing
  free-surface amplification. `sensor_depth_km` is a static input, so the model can learn it.
- **Saturation.** At M6–8, the median residual is −0.47 dex and the Mw slope is 0.67 against 0.92
  for ML. The 3 s P amplitude grows more slowly than magnitude for large events; the 1–45 Hz
  pre-filter contributes (see Known issues).

### Gain QC (`gain_qc.npz`, analysis only)

- An epoch is one station, family and sensitivity combination. 2,255 epochs have at least 10
  records. **39 of them sit more than 1 dex off the global fit**: likely wrong metadata, such as
  HT.EVGI, PR.TBVI, OK.W35A, ET.BCRT or AF.DODT.
- They hold 6,148 records (0.6%), including 16 M≥5 records from 16 events.
- These records were **not dropped**, because the check uses magnitudes from every fold.
  `suspect` is row-aligned with the cache if a run wants to exclude or stratify them.

## Known issues

1. **1–45 Hz pre-filter (STEAD processing).** Energy below 1 Hz is attenuated. This lowers large
   events' P amplitudes and makes saturation stronger than in raw INSTANCE counts. It applies to
   every record and cannot be undone.
2. **Mixed magnitude scales.**
   - The bulk is ML/Md (95% of records) and the tail is mostly Mw.
   - 151 of the 718 M≥5 events are labelled **mb**, which saturates near 6 and has the largest
     scatter.
   - For an Mw-only tail, filter `mag_type` at evaluation: Mw* covers 525 M≥5 and 56 M≥6 events.
3. **Few records per large event.** M≥5 events have 2.3 records on average and M≥6 events 1.9.
   STEAD stores one station per event in 52% of all events. The tail is broad across events
   (good for event-level bootstrap) but thin per event, so multi-station fusion has little to
   work with at M≥5.
4. **Horizontals are not rotated.** Borehole PB stations record EH1/EH2 at arbitrary azimuths
   (mapped 1→N, 2→E). The amplitude features use all-component RMS, so this matters only for
   the shape input.
5. **Location ambiguity.** Traces at stations whose location codes have different gains were
   dropped (4,474). Same-gain location codes take '' or '00' first; only the native rate and
   sensor depth come from that choice.
6. **Overlap with INSTANCE.** STEAD contains Italian IV stations and Italian events, such as the
   2009 L'Aquila sequence. That is irrelevant for within-STEAD CV, but matters for any
   cross-catalogue transfer test.
7. **`train.py --amp-aug` clamps labels to [0, 7].** That clips 238 records with M<0 and 3 with
   M>7. Without amplitude augmentation it does nothing.
8. **Ephemeral storage.** The cache lives on `/mnt/scratch`, which is wiped when the instance stops.
   The rebuild command is at the top of this file.
