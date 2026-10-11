autoreview findings: 2
[P2] P2: Bind selection eligibility to the original census fields
work/geonet_clock_paired_independent_audit/audit.py:161
Selection is reconstructed entirely from bulk_plan["rows"]. The pinned census rows and groups are never used to verify magnitude or calendar partition; the preceding loop compares only outcome bases. Consequently, a producer error that copies a complete candidate's magnitude below 6 or changes its partition can remove it from the control pool and select another control while every implemented check passes. Hash verification preserves that error rather than detecting it. Verify the original eligibility fields against the census before ranking candidates.

[P2] P2: Reject non-scalar native originReference evidence
work/geonet_clock_paired_independent_audit/independent.py:282
Native originReference values bypass the scalar-container validation and use only Element.text. For example, replacing the invented fixture's reference with <originReference>invented-o<x/>different</originReference> still passes reference membership and linkage checks because the child and trailing text are discarded. This reports supported raw-core linkage for a reference whose complete text is different and whose structure is outside the scalar profile. Require each originReference to have no child elements before using its text; otherwise classify the raw core as unavailable.

overall: patch is incorrect (0.93)
Static inspection found two defects within the advertised selection and raw-core scope: original eligibility fields are not independently checked, and native reference parsing can discard evidence while certifying linkage. No actual data was inspected or tests executed.
