# Post-clean semantic v2 static limitation receipt

This separate packet checks the unchanged independent semantic v2 source with invented XML only. It is not a new source version, review, or actual-data result. No actual inputs, producer implementation, credentials, clocks, data acquisition, XSLT execution, schema validation, or shared Git changes occurred.

Twenty invented cases passed under the pinned Python 3.14.5 runtime. All 59 files in the frozen semantic v2 allowlist match their prior pins and stayed byte-for-byte unchanged before/after these checks. The first scratch-harness attempt used a nonexistent output label; its failure is preserved, and only the new harness was corrected to use the existing `paired_recorded_revision_resolution_count` interface. No frozen bytes or review evidence changed, and no further autoreview ran.

The requested three checks found no reproduced defect:

- Native 0.10/0.11 whitespace-only text in all seven event/origin creationInfo fields becomes empty candidate text, with the parsed raw lexical text retained. Empty URI fields subsequently use the pinned optional-ID NA mapping. Nonempty padded text and non-XML whitespace remain literal.
- Foreign-namespace nodes carrying colliding publicIDs in native 0.10/0.11 and QML return unknown. Those inputs are excluded by the conservative foreign-namespace guard before global-ID processing; this demonstrates no unsafe ignored collision, not general foreign-format coverage. Supported extension and root-wide outside-scope mapping collisions also return unknown.
- Latitude, longitude, and depth negative zero/positive zero have the same canonical zero. This agrees with the new public producer v2 signed-zero policy.

An adjacent static contract gap does reproduce: the frozen auditor accepts an XML-namespace `space` attribute anywhere in the root. With `xml:space="preserve"` on a native root or creationInfo, it strips a whitespace-only author candidate, and comparison against an invented empty-author QML member can return `same_record_content=true`, `revision_evidence=matching_recorded_revision`, and `paired_recorded_revision_resolution_count=1`. The new public producer v2 protocol/specification require such inputs to be unknown. No transform was executed, and no actual body is asserted to contain this attribute.

**Current unguarded actual use is barred.** A narrow alternative is a separately reviewed and pinned bounded joint invocation that rejects any `{http://www.w3.org/XML/1998/namespace}space` attribute anywhere inside the parsed document root before either projector. Excluded members remain unknown/null and cannot promote recovery. The joint invocation must preserve every other declared policy difference, source/runtime/input/profile pin, limit, and parent-owned actual-read gate. This exclusion supports only the remaining supported subset and does not establish universal equality.

If projection-level support is needed, prepare a separately versioned directory/source that excludes xml:space, with invented tests and a first-clean review; preserve frozen semantic v2 unchanged. This receipt does not authorize that work or actual reading. Physical timing, atomic database revision, deployed converter, complete schema validity, model improvement, and original-result rewrite claims remain false.

Replay command (writes only this new packet's receipt):

```
work/geonet_waveform_feasibility/.venv/bin/python -B work/geonet_legacy_semantic_v2_static_limits/invented_static_checks.py
```

`static_limit_receipt.json` records the individual cases and source/runtime/public-document pins. `SHA256SUMS.txt` pins this packet's six public files; it is intentionally excluded from its own checksum list. The runtime pins and receipt are diagnostic evidence, not a new independent code review.
