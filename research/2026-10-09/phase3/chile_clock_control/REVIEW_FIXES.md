# Review v1 runtime-record contract

The v1 reviewer correctly identified that the included plain trainer emits no station_backend field. The sole accepted run.json is the pinned completed migration, whose wrapper source was missing from reviewer context. The source-only wrapper flat_station_runtime.py wraps runtime_identity with station_backend.strict_runtime. This control continues event training via HDF and does not install that station-pretraining backend.

The guard now explicitly requires the recorded migration schema and scope, requires the three recorded precision settings, preserves exact runtime comparisons, and gives a fail-closed ValueError for a plain or incomplete record. An invented test verifies valid migrated context, missing/wrong extension and precision mismatch. No production receipt was accessed by the closeout agent; parent verifies the frozen run hash and actual runtime before fitting.

Review v2 includes wrapper source context SHA 43e65f551c02f7eb49fc1c02ae03f051b438146d98d901776a8144a05eecfd2c. Original protocol SHA 8d4e2e3ed43c072356d539bb822316ed8f8d2cee3213ff8a02ef419a6f33777b is unchanged. Local invented tests: 28 run, 27 pass, one h5py skip; this is not production readiness.
