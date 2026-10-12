# Pure API and private result contract

`scanner.scan(raw)` accepts exactly builtin `bytes`. It performs no IO, network, vendor import, payload decoding, timestamp conversion or source fetching. Type/subclass failures do not call input hooks. Empty and over-cap inputs return unknown. The root proposal is normative; this document spells the implemented return shape.

Every result is a builtin dict with exactly these keys: `disposition` (`supported` or `unknown`), `reason`, `header_layout_count_ledger_supported`, `body_bytes`, `body_sha256`, `failure_ordinal`, `record_count`, `advertised_samples`, `records`, and the eight false claim keys below. Builtin bytes of admitted size are hashed even when structurally unknown. Invalid types have null body size/hash; empty bytes have size zero and their SHA256; over-cap bytes have their integer size and null hash, avoiding unbounded hashing. Failure ordinal is zero-based within the original sequential body; type/empty/raw-size failures use null.

Reason codes are only `supported`, `input_type`, `empty`, `body_byte_cap`, `record_cap`, `truncated_header`, `literal_header`, `header_structure_unknown`, `ambiguous_endian`, `mixed_layout`, `sample_cap`, `output_cap`. An unknown result has zero qualified records/samples and an empty records list, with no partial promotion, input contents, exception text or candidate details. SHA256 is custody information, not an authenticity or decoding proof.

Every supported record descriptor is a builtin dict with exactly:

- `ordinal`, `offset`, `length`, `endian` (`big` or `little`), `sequence`, `quality`.
- `nslc`: `[network, station, location, channel]`, strict literal strings after right-space field padding. Blank location is `""`.
- `date`: `[year, day_of_year, hour, minute, second, fraction_0_0001_second]`; `date_unused`: the raw unused byte. No guessed UTC clock or nanosecond conversion.
- `npts`: the unsigned advertised count; `rate`: signed `[factor, multiplier]`; `flags`: unsigned `[activity, io, data_quality]`; `correction`: signed raw 32-bit correction.
- `data_offset`, `blockette_offset`, `blockette_count`, `encoding`, `word_order`, `b1000_reserved`.
- `b100`: null, or `[finite_positive_float32_rate, unsigned_flags_byte, reserved_byte_1, reserved_byte_2, reserved_byte_3]`.
- `b1001`: null, or `[timing_quality_0_to_100, signed_microsecond_byte, reserved_byte, frame_count_byte]`.

These descriptors are PRIVATE for any future actual invocation. Public parent reporting must expose only generic counts/dispositions. There are no payload bytes/arrays or mutable input aliases. Each call and record owns its result lists/dicts.

The supported body has exactly one complete structural endian interpretation per record, uniform length/header endian, an explicitly enumerated chain with unique 1000 and optional unique 100/1001, integer count/sum, exact boundaries and fixed-width capacity checks. Header-only STEIM recognition does not check packing, frame capacity or decode correctness. Zero advertised counts are retained.

Always false, including successful scans: `payload_admission_verified`, `raw_record_timing_verified`, `decompression_admission_verified`, `hard_RSS_verified`, `physical_calibration_verified`, `waveform_coverage_verified`, `model_input_verified`, `novelty_verified`. Only `header_layout_count_ledger_supported` can become true.

Caps are 8,388,608 raw bytes, 32,768 records, 8,000,000 advertised samples, 16 links per record, record lengths 256 through 1,048,576, and 16,777,216 bytes for canonical ASCII JSON output (sorted keys, compact separators, no NaN). Descriptor-ledger and whole-result caps are both checked. Output caps do not prove Python/native RSS. Parent-owned seventeen-body accounting, runtime publication, private custody, decoder containment and independent qualification remain separate.
