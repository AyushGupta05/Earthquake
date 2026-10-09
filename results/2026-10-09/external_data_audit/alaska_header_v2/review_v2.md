autoreview clean: no accepted/actionable findings reported
overall: patch is correct (0.92)
The scoped change symmetrically aliases only empty/-- locations, preserves decoded raw identifiers, rejects ambiguous identities within each source, and retains actual sample rates with signed deviations. No actionable regression or security defect was found. Review was read-only; tests, the real archive audit, and GPU work were not run.
