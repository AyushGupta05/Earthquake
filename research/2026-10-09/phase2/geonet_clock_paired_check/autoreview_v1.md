autoreview findings: 4
[P2] [P2] Reject foreign namespaces for all evidence-bearing fields
work/geonet_clock_paired_check/projection.py:26
CRITICAL omits fields that directly affect acceptance and revision evidence, including native weight, evaluationStatus and creationInfo. For example, replacing a native zero weight with {foreign}weight makes projected_weight treat it as absent, allowing the pick to be accepted while the representation remains status='ok'. A foreign evaluationStatus containing 'rejected' is similarly ignored. Extend the namespace guard to the evidence-bearing fields so these substitutions produce unknown_representation, as required by PROTOCOL_v1.md.

[P2] [P2] Preserve the frozen census clock independently of shadow parsing
work/geonet_clock_paired_check/comparison.py:71
The preserved original anchor is obtained exclusively from the newly parsed original representation. If the stricter parser classifies that body as unknown_representation, every at_preserved_original_T0 result becomes null, even when the verified original census outcome contains an accepted-subset NZ T0. This is an explicitly supported case: unsupported original bodies remain in the diagnostic. Carry the checksum-bound census T0 through the plan and use it independently of the original shadow projection's status.

[P2] [P2] Include the event identity in scoped mapping collision checks
work/geonet_clock_paired_check/projection.py:269
The collision map includes origin references and scoped pick identifiers, but omits the selected event's publicID. A native event named 'invented-event' and its referenced origin named 'smi:nz.org.geonet/invented-event' therefore map to the same projected identifier without triggering ID_mapping_collision. The parser returns an ordinary representation despite the protocol requiring mapping collisions to remain unknown. Include the event identity in the scoped raw-to-mapped collision map before accepting the representation.

[P2] [P2] Preserve lexical creationInfo values for revision comparisons
work/geonet_clock_paired_check/projection.py:133
creation() reads every field through scalar() with its default strip=True. Consequently, distinct recorded author, agencyID or version strings such as 'Analyst' and ' Analyst ' become equal. With equal recorded timestamps, compare() can then report matching_recorded_time and a paired recorded-revision resolution count instead of retaining the lexical conflict. Preserve the creationInfo text used for comparison so normalization cannot erase known revision differences.

overall: patch is incorrect (0.95)
The diagnostic has actionable gaps in namespace validation, scoped ID collision detection, preservation of the original census clock, and conservative revision comparisons. These can accept unsupported evidence or misstate comparison results. Review was read-only; no tests, acquisition, transforms or nested reviewers were run.
