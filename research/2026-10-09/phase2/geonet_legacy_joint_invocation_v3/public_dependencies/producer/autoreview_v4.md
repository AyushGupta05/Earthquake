autoreview findings: 1
[P2] [P2] Bind the candidate pick to the exact raw arrival target
projection.py:585
The raw-reference guard checks only multiplicity, so it can validate a different object from the one returned by the trimmed candidate lookup. For example, let a native P arrival reference `smi:invented/p `, whose exact pick is rejected, and let an amplitude select a separate valid NZ pick named `smi:invented/p`. Both IDs pass the untrimmed collision guards. The arrival candidate becomes `smi:invented/p`, `native_raw_reference_matches` is 1, and this condition passes using the other pick. The rejected arrival is therefore accepted with another object's station and time, corrupting coverage, clocks and recovery counts. Require the retrieved pick's raw publicID to equal the arrival's raw pickID, or retain the exact raw target through lookup; a trimming-induced substitution must remain unresolved.

overall: patch is incorrect (0.98)
The comment/PI parser policy matches the stated contract, but native reference validation permits a concrete pick substitution after candidate trimming. This violates the exact raw identity guard and can produce incorrect diagnostic counts and clocks. Review was read-only; no tests or transforms were executed.
