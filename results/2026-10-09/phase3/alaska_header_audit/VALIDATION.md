# Header auditor validation

This prepares the parent-owned audit; it does **not** audit the real MiniSEED containers. Only synthetic in-memory waveforms and the previously saved `archive_index.json` were read. The parent must finish the full ZIP download, verify its published identity and launch the real audit.

The initial six tests exposed an ObsPy fixture API error in five tests (`AttribDict.update` requires a mapping). Inspection of the saved central directory also found the original join used the whole waveform stem, including `_replay`, against bare metadata IDs; this rejected all event pairs before processing. Both are fixed. An additional logic correction caps a nested segment's overlap duration at its own duration instead of the distance to the accumulated coverage endpoint.

The pure naming check now maps all 781 `<id>.dat` files to 781 `<id>_replay.seed` files. It rejects duplicate names, unexpected member suffixes and nested/colliding IDs. The maximum recorded uncompressed MiniSEED member is 45,134,848 bytes, below the existing 50,000,000-byte member limit; all metadata files also fit. No waveform payload was accessed to establish these facts. Exact directory-index hash and counts are in `index_contract.json`.

Ten tests passed in 0.013 s under `work/alaska_venv/bin/python`:

- Existing count/unit/SCNL, gap, overlap, rate and metadata checks.
- Actual release naming and rejection cases.
- Explicit `obspy.read(..., format='MSEED', headonly=True)` call, plus rejection if nonempty sample arrays are unexpectedly returned.
- Full synthetic ZIP member CRC validation before header parsing; corrupting a stored member raises `BadZipFile`.
- A nonempty partial header stream accompanied by a reader warning is rejected. Review found this real completeness issue in ObsPy; the installed dependency regression test confirms skipped records can return a nonempty stream. All reader warnings now conservatively fail the audit, requiring explicit inspection before any gate is relaxed.

Installed ObsPy 1.5.1 source confirms `_read_mseed` sets `unpack_data=0` when `headonly is True` and passes that flag to libmseed. See `reader_contract.json`. Synthetic fixture creation encodes invented samples only; the real audit performs no waveform sample decoding, picks, inference or use of magnitude labels.

The command's fixed full-release size/MD5 gate remains before output creation. Selected members are read to EOF, so Python checks their CRC. Both metadata and waveform CRC/size are recorded. `events.json` is written atomically, followed by a last-written atomic `COMPLETE.json` containing its SHA256 and runtime/source identities. A failed/incomplete run has no completion marker. These 781 release containers remain distinct from the unresolved published 530-event cohort and the 780 current ComCat identities; no cohort selection or alias deduplication is performed.

Autoreview result and final source hashes are recorded separately in `verification.json` after review completion. No GPU runs, actual archive audit or commits were performed in this subtask.
