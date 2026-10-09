# Read-only investigation of the Chile input pipeline

The live, authoritative baseline is unchanged. Its CPU and I/O measurements suggest a serial input pipeline is limiting station pretraining. They do not establish the exact fraction of time spent in LZF decompression, HDF metadata lookup, Python, CUDA launch overhead, or transfer. No stack profiler was attached, no cache was flushed, and no disk was formatted or mounted.

## Evidence

A 31-second observation during full pretraining (19:37:21–19:37:52 UTC) found:

| Measurement | Observation |
|---|---:|
| Training process CPU | 74.23% of one core; four CPUs available |
| Whole-machine CPU idle | 74.7–75.1% |
| Whole-machine I/O wait | 6.4–6.5% |
| GPU utilization, four samples | 9%, 15%, 7%, 17% |
| Process logical read traffic | 67.3 MiB/s |
| Process physical read traffic | 39.9 MiB/s |
| Read system calls | 2,282/s |
| Root-device reads | 350–369 IOPS |
| Root-device read latency | 0.96–0.97 ms |
| Root-device utilization | 27.4–27.7% |
| Training-process resident memory | approximately 1.77 GiB |
| System file cache | approximately 12.95 GiB |

These counters are inconsistent with GPU compute saturation or saturation of the provisioned EBS throughput/IOPS. They are consistent with serialized host work and reads supplying an intermittently active GPU. GPU values are sparse utilization samples, not a continuous trace. The logical/physical byte difference is not an exact cache-hit fraction because readahead and metadata traffic also contribute. Raw evidence is `full_run_io_sample.json`.

The reviewed `StationDataset.__getitem__` at `train_team_lm.py:224` maps the station index, performs a pandas row lookup, then creates a temporary waveform dataset and selects one station. The file handle survives, but the waveform dataset handle does not. The batch loader has `workers=0`, and transfer/model/gradient work follows the completed CPU batch.

The observed cache layout is **float32, LZF plus shuffle, chunks `(8,3000,3)`**, with an 8 MiB raw chunk cache per dataset. One desired station is 36,000 bytes; its uncompressed chunk is 288,000 bytes. HDF processing involves the entire chunk even when selecting only part of it. This is an eight-to-one chunk footprint relative to the requested station, not a claim of eightfold wall-time overhead. [h5py chunk documentation](https://docs.h5py.org/en/latest/high/dataset.html#chunked-storage)

Closing the final dataset reference clears its raw chunk cache, while file metadata and OS caches can remain. Thus merely increasing the cache size will not provide cross-item chunk reuse with the current temporary-dataset access pattern. [HDF Group explanation of dataset-close caching](https://forum.hdfgroup.org/t/reset-chunk-cache/12424)

This differs from the author runtime: the original training script loads waveform arrays before fitting and concatenates a station array for pretraining; the Chile configuration requests ten generator workers. The port preserves its documented data/objective choices while using lazy HDF reads on a much smaller host. Absolute runtime is therefore not a replication of the authors' runtime. [Author training code](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/train.py#L226), [author Chile configuration](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/magloc_configs/chile_mag_noloc.json)

## Small correctness/throughput probe

One CPU-only probe sampled 512 distinct fitting-TRAIN events uniformly, then one station from each, using seed 20261009. This is an event-uniform probe, not the actual station-uniform epoch permutation. It used independent read-only HDF handles in spawned processes, no Torch or GPU, no DEV waveform reads, and an external 55-second timeout plus five-second termination grace. Total execution was **2.894 seconds**.

| Reader | Wall seconds, including setup | Sum of per-item reader seconds |
|---|---:|---:|
| Serial initial pass | 0.891 | 0.890 |
| Serial repeated pass | 0.558 | 0.557 |
| Two spawned processes | 0.581 | 0.683 |
| Four spawned processes | 0.539 | 0.896 |

All 512 arrays were compared element by element, with matching shape/dtype and order. Their ordered SHA-256 was `a473ead566da87aa339384aff47717a232524edaf9edc4789da8511f8f20340a` in all four cases. The probe measured raw HDF reads, excluding pandas lookup, Torch collation, training and optimizer behavior. The fixed case order warmed OS caches; parallel timings include spawn/import/IPC. The tiny test **does not demonstrate a meaningful multiprocessing wall-time improvement** or establish training equivalence. Evidence is `cpu_loader_probe.json`; the standalone script is `work/team_loader_probe.py`. Its isolated Codex autoreview returned clean, confidence 0.96.

## Minimal alternatives for a later version

| Alternative | Measurable hypothesis | Required test and provenance |
|---|---|---|
| Persistent prefetch with two workers | Overlap input preparation and GPU work, then test whether spare CPUs help beyond pool startup | A new bounded TRAIN-only run, same sample order/batches and recorded worker setting; at least 100 timed batches plus a warm epoch. Compare tensors, cutoffs, labels, gradients and optimizer state before claiming equivalence. |
| Keep the last dataset open during ordered station calibration | Reuse an eight-station chunk while adjacent stations are evaluated | Compare complete ordered calibration inputs and proper scores; keep the handle cache bounded. This targets calibration. Random TRAIN sampling has little adjacent-event reuse, so do not project its gains onto training. |
| A separate station-aligned derived cache or flat float32 array | Remove repeated eight-station decoding and many HDF object lookups | Verify every derived station tensor against the frozen source, preserve canonical station/event order and labels, bind source/derived hashes and exact split membership, then test full batch/optimizer equivalence. Never rewrite the authoritative cache. |

Increasing only raw chunk-cache capacity is not a promising first step because it is already 8 MiB and the relevant dataset closes per sample. Moving only the existing compressed file to faster storage can reduce read latency but leaves the decoding and object-lookup pattern unchanged. A larger GPU alone would not address the measured low GPU utilization.

Read-only `lsblk` also found a **232.8 GiB Amazon EC2 NVMe instance-store device**, `nvme1n1`, with no reported filesystem or mount. It was not initialized or used. It is a possible location for a future regenerable station cache; a flat fitting-station float32 array would require about 27.96 GB before metadata. Instance-store capacity is included in the instance price, but its data are lost on stop/hibernate/termination. Original data, manifests and recovery checkpoints must remain on persistent storage. [AWS instance-store documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html), [AWS persistence rules](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-store-lifetime.html)

## Provenance and recovery implications

The current run remains `team_transformer_06742dc492a1_7ec986ada2e7`, with its exact audited CLI and deterministic settings. Its first completed epoch is the next appropriate point for a runtime revision. Do not change data loaders, cache paths, worker count or code underneath it.

Epoch recovery compares the entire run configuration, source hashes, data hashes, runtime and split identity. Changing `--workers`, changing `StationDataset`, or using a different cache in an existing run should therefore be a **new run/version**, not an unchecked continuation. Use the already prepared exact recovery command only with the original configuration.

Encoder compatibility is narrower: `StationDataset` is explicitly included in the pretraining implementation fingerprint. A loader implementation change invalidates that fingerprint even if a small tensor test passes. Worker count is retained in the origin configuration but is not part of the narrower encoder pretraining identity. Do not confuse accepted encoder import with proof that two training executions are bitwise equivalent. Any intentional compatibility migration needs its own reviewed evidence and explicit versioning; do not bypass current checks.

For a future optimized reproduction, preserve the authoritative baseline, validate complete data identity, test fixed-RNG parameter/optimizer equality in a controlled environment, and report any remaining numerical differences. A faster data reader is an engineering improvement, not an earthquake-method novelty claim.
