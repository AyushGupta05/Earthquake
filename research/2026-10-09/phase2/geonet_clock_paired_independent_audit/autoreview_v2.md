autoreview findings: 3
[P2] Do not swallow the auditor deadline as unavailable XML evidence
work/geonet_clock_paired_independent_audit/audit.py:258
The SIGALRM handler raises AuditError("auditor_deadline"), but this handler catches every AuditError raised during xml_core and continues with an unavailable slot. If the 300-second alarm fires during XML processing, the one-shot alarm is consumed and the audit can subsequently return all_scoped_checks_pass=true. The parent's 330-second watchdog does not prevent a successful return between those deadlines. Propagate deadline errors so resource exhaustion produces a failed scoped check.

[P2] Reject non-UTF8 XML encoding declarations
work/geonet_clock_paired_independent_audit/independent.py:229
Decoding the bytes as UTF8 does not validate the XML encoding declaration. ElementTree receives a Unicode string here, so a UTF8-decodable document declaring ISO-8859-1 can still produce a supported core. This contradicts the documented non-UTF8 exclusion and can derive incorrect lexical revision fields when non-ASCII bytes are interpreted differently by the producer's byte-based XML parser. Validate the declaration before parsing and classify unsupported encodings as unavailable.

[P2] Restrict QML modificationTime to the supported native namespaces
work/geonet_clock_paired_independent_audit/independent.py:296
For QML, the first branch accepts every revision field in the BED namespace, including modificationTime. Consequently, a BED-only modificationTime is accepted and can yield matching_recorded_time even without another valid recorded time. PROTOCOL.md explicitly permits this native extension under BED creationInfo only in one of the two supported SCML namespaces. Exclude BED modificationTime from the ordinary-field branch and reject it as unsupported evidence.

overall: patch is incorrect (0.98)
Read-only inspection identified a swallowed soft deadline and two XML-profile false positives within the auditor's stated verification scope. No tests, private-input reads, network access, or nested reviews were performed.
