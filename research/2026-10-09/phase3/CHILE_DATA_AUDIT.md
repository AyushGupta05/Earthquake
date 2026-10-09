# Chile TEAM-LM data audit

The official Northern Chile benchmark was acquired, verified and exported locally on 9 October 2026. Both training/development caches are ready. TEST waveform values remain uninspected and are absent from both caches. No model performance or novelty claim follows from this data audit.

## Source, licensing and reproducibility

- Data: Münchmeyer, Bindi, Leser and Tilmann (2021), [Fast earthquake assessment dataset for Northern Chile](https://doi.org/10.5880/GFZ.2.4.2021.002), **CC-BY-4.0**. Cite this dataset and [the TEAM-LM paper](https://doi.org/10.1093/gji/ggab139) in derived research.
- [Official archive](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2021.002noeUVRE/chile.tgz): 42,902,965,249 bytes, SHA256 `079132f8cce16c7bb81188969b93f8e07ea9fb297a705f2a8e6e61ef715614df`.
- Raw HDF5: 115,893,796,855 bytes, SHA256 `f964cba056e1c5fe550d3536cc73028d51a3a669a3e0ef2e725a0224470212da`.
- The archive contained only `chile_filtered.hdf5` and a 68,666-byte README.pdf. Its gzip CRC/length and the archive-member SHA against the extracted file passed. The compressed archive was then removed with authorization; raw data and both caches remain locally within the 160 GiB task limit.
- Published split convention: [TEAM loader](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/loader.py), **GPLv3** source. The new exporter records that convention explicitly. Source-derived model code must retain appropriate author/license attribution.

Small machine-readable evidence is in `results/2026-10-09/phase3/data/`; no waveform dataset is committed to Git.

## Exact split and high-magnitude support

The HDF5 contains 96,133 unique EVENT IDs in increasing TIME order. The published default loader splits by **row position**: `test_start=int(.7*N)=67293`; `train_end=int(.6/.7*test_start)=57679`.

| Split | Events | MA ≥ 5.5 | MA ≥ 6 | MA ≥ 7 | MA ≥ 8 | Maximum MA |
|---|---:|---:|---:|---:|---:|---:|
| TRAIN | 57,679 | 22 | 12 | 1 | 1 | 8.054 |
| DEV | 9,614 | 1 | 0 | 0 | 0 | 5.715 |
| TEST | 28,840 | 30 | 12 | 3 | 2 | 8.274248 |

The existing metadata `SPLIT` column is an unrelated randomized catalog split and must **not** select benchmark membership. The pandas index is also nonunique. The added 2014-04-01 mainshock has a null native SPLIT. Cache `benchmark_split` and `source_row_index` are the authoritative explicit membership fields; do not rerun the 60:10:30 formula on the shortened cache table.

DEV contains no MA ≥ 6 events and one MA ≥ 5.5 event. Tail model selection needs a preregistered, event-separated split within TRAIN or an independent region; TEST must not serve as calibration data. MA is an amplitude magnitude label, not interchangeable with ML or Mw. Published TEAM values at 1 second cannot be compared directly to INSTANCE single-station scores, and the paper's tabulated times omit 3 and 5 seconds, requiring a matched rerun.

## Waveforms, coordinates and timing

All 96,133 groups have exactly `coords`, `stations` and `waveforms`, with no missing metadata IDs. There are 1,605,983 station records, 8–21 stations per event. Raw waveforms are float64 `[stations,3000,3]`, 100 Hz, ZNE, sensitivity-corrected velocity in m/s; instrument response is not removed. All stations share a window starting 5 seconds before the network's first P arrival and ending 25 seconds after it.

Coordinates are `[latitude degrees, longitude degrees, depth km]`, WGS84, depth positive below sea level. Station coordinates and identifiers are copied exactly. There are **no per-station P-pick arrays**. Chile's published configuration leaves trigger gating disabled, so continuously streamed prearrival noise is eligible. Do not invent future-informed picks or station selection.

The caches contain raw, uncentered float32 values, with no filtering, scaling, station selection or other signal changes. Prefix centering and peak normalization belong in the causal model/loader, using only samples before each cutoff. The strict exclusive cutoffs for 1/3/5 seconds are 600/800/1000 samples. Pad compact inputs to 3000 for the source TEAM encoder; full inputs already have that shape.

## Ready caches

| Cache | Samples | Window | Bytes | SHA256 |
|---|---:|---|---:|---|
| `chile_train_dev_prefix1000.hdf5` | 1000 | −5:+5 s | 10,083,869,081 | `eec94c8ea5faeea023e300fc5603f1342f9da85cb45a70ec4dcd8bbe4d4da37d` |
| `chile_train_dev_full3000.hdf5` | 3000 | −5:+25 s | 30,432,938,039 | `c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb` |

Both caches contain 67,293 TRAIN+DEV events and 1,049,297 station records. Schema is `chile-team-prefix-v1`; root attribute and manifest `stored_samples` are 1000 or 3000. `metadata/time_after` is correspondingly 5 or 25. Original `time_after=25` is retained as root `source_time_after_seconds`.

Each cache stores a pandas table at `metadata/event_metadata`, groups at `data/{EVENT}/...`, and `splits/{train,dev}_event_ids` plus `splits/{train,dev}_source_rows`. Use the full cache for the original random training cutoffs through +25 seconds or a training-only future teacher. The compact cache supports an early-window training adaptation.

### Metadata sidecar for the AWS runtime

AWS Python 3.9/PyTables 3.9.2 is incompatible with the shared NumPy 2.0.2 wheel. The shared training environment was not downgraded. Each cache instead has an adjacent `<cache>.metadata.csv` and `<cache>.metadata.csv.manifest.json`; this avoids PyTables at training time without changing the cache bytes or hashes.

Both CSVs contain exactly `EVENT,MA,TIME,source_row_index,benchmark_split`, 67,293 TRAIN+DEV rows, and are 4,129,245 bytes with identical SHA256 `8840a482419afff5a54681beeb901e5a227e12e64cdf76b1faddf5b3d38285a1`. Each manifest binds the CSV to the corresponding cache SHA256 and records `origin=metadata/event_metadata`, row/column counts and provenance. Small copies of these manifests are committed in the data-results directory; CSV data stay outside Git.

Sidecars were generated with Python `csv.writer` from the verified local cache table, preserving Python float round-trip strings. `pandas.read_csv` with `float_precision='round_trip'`, MA/TIME float64, source_row_index int64 and string IDs/split fields matched the source dataframe exactly. EVENT IDs and source rows also matched both HDF split lists. The training loader should check the CSV and cache checksums and these exact memberships before using the sidecar. No TEST rows or waveform values enter it.

## Verification and commands

Every exported waveform was read back and compared exactly to the source slice cast to float32. Every coordinate and station identifier also matched exactly. Maximum absolute float32 conversion error was 9.313e-10 m/s in both caches; no nonzero source values underflowed to zero. Independent full-file SHA256 and reopened membership checks passed. A deterministic 69-event sample, including split boundaries and the largest TRAIN event, confirmed identical first-1000 waveforms, coordinates and station identifiers across caches. No TEST waveform values were read.

```sh
python research/2026-10-09/phase3/export_chile_prefix.py \
  --source /path/to/chile_filtered.hdf5 \
  --source-manifest /path/to/chile_source_manifest.json \
  --output /path/to/chile_train_dev_full3000.hdf5 \
  --samples 3000 --max-bytes 40000000000
python -m unittest discover -s tests -p test_chile_export.py -v
```

The exporter requires h5py, numpy, pandas and tables. Its source manifest must record completed extraction and verified gzip CRC. It refuses existing outputs, checks source size, checks finite inputs, enforces explicit splits, and publishes with no-replace hardlinks. It expects the independently verified source file described above; it does not rehash the 116 GB source on each invocation.

All 12 focused tests passed. Codex autoreview of the standalone exporter and tests returned zero findings after fixing two accepted publication issues (late output collisions and manifest-failure cleanup). The final review command used the standard autoreview helper in local mode with Codex, plus the focused unittest command; its structured result is saved as `data/exporter_autoreview.json`. Repository integration changes only the test import path; focused tests were rerun there. Exact TensorFlow numerical equivalence, training reproducibility and model superiority are separate validation tasks.
