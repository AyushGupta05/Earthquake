# Source-only curation

Allowed publication/review: authored auditor, invented in-memory fixtures, authored protocol/README/gate, byte-exact root/public collector contract documents, exact source/runtime/test/review pin receipts and generic safe metadata. Prior V4 source was read only as an authored baseline; collector implementation/tests were never read/imported.

Excluded: any actual local_runs directory, rows, IDs, keys, event clocks, plan/auth/receipt/result, inventory/XML, body/waveform, credentials, account configuration, raw third-party source, .git object/history internals, __pycache__, helper temporary/transcript files, review incidental outside-workspace content. Review takes place in a fresh isolated .git repository; its .git internals are not published. No shared Git mutation or external source execution occurred. Safe allowlist controls copying; arbitrary filesystem enumeration is not an actual-input reader.
