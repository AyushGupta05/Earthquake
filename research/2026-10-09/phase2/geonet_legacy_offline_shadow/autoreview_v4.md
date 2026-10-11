autoreview findings: 2
[P2] [P2] Detect same-type duplicate identities outside the projected scope
projection.py:311
A colliding outside object with the same type and raw publicID disappears into these sets. For example, adding a BED pick under eventParameters with the same publicID as the event's scoped pick leaves both sets unchanged. The projected picks dictionary still contains one record, so analyse accepts the reference and comparisons can report a newly unique object despite the duplicate identity. This bypasses the protocol's outside-scope collision and duplicate-pick safeguards. Track object multiplicity for colliding outside identities and invalidate correspondence without projecting those objects.

[P3] [P3] Preserve the original text in raw timestamp fields
projection.py:264
raw_time calls quantity(), which uses scalar() with strip=True, so it duplicates the normalized time field instead of retaining the raw lexical value. A padded timestamp and an unpadded timestamp produce identical raw_time values, losing the evidence needed to distinguish source text from projection normalization. QML raw_preferred_origin_id similarly reuses the stripped preferred value. Read these raw fields with strip=False and keep normalization confined to their candidate counterparts.

overall: patch is incorrect (0.95)
Outside-scope duplicate identities can incorrectly establish unique correspondence, and some fields labeled raw discard their original lexical values. Review used read-only source inspection; no tests or transforms were executed.
