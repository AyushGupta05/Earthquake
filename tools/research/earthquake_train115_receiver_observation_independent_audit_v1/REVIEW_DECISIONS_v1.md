# Accepted review1 finding

Review1 correctly identified horizon-dependent concatenation dtype promotion for valid continuous mixed i4/f4/f8 records. All original raw/native/per-piece hashes remain exact. The redundant early-prefix scalar comparison now uses lossless float64 representation, because every supported i4/f4/f8 scalar is exactly representable in binary64. This does not replace native hashes or change feature mathematics. Added full115 invented i4-to-f8 and f4-to-f8 replays; all29 tests pass. No candidate implementation/test or actual data was read. Review1 is retained.
