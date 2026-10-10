# Independent response-export metadata audit

This check compares the completed 112660-row TRAIN export with the frozen
polarization population and corrected v3 response metadata. It does not run the
exporter or import its validation functions.

The script pins the export manifest, metadata NPZ and v3 join audit to the exact
parent-authorized hashes. It verifies the referenced population NPZ, selected CSV,
epoch/evaluation JSON and existing join CSV bytes. The large join CSV is read from the separately transferred
`/home/ec2-user/response_export_audit_inputs_v3/` input directory and must match
the corrected audit's stored hash; it is not part of any source/review bundle.
It loads only allowlisted NPZ
metadata members. `counts.npy` is never opened; the `features.npy` matrix is never
decoded. Hashing the containing population NPZ is a byte-level integrity check.

Checks cover all ordered source/trace/event/station IDs, hash partitions,
restoration weights and denominators, magnitude labels, per-deadline validity
and reason codes, scalar sensitivities and units. All 34 static columns are
reconstructed from selected CSV fields and the referenced epochs. All 72 response
columns are matched to v3 epochs; each saved epoch mask is independently rebuilt
from its stored evaluation, sampling rate and six fixed frequencies. Invalid
response descriptors must be exactly zero, and valid phase features must have
unit norm. Referenced epochs must match ENZ SCNL identities and cover the complete
seven-second metadata window. The existing v3 join is scanned to confirm every
selected record uses its corrected matched epoch IDs.

This does not recompute evalresp or prove raw-stream causality. Full-waveform
contents and the huge raw HDF hash remain outside this audit. There are no model
fits, GPU calls or DEV/TEST reads. Run remotely with two BLAS/OpenMP threads under
`timeout 180`; stdout is the audit receipt, saved only in this audit directory.

The response architecture and exposure objective comparisons preserve separate
frozen magnitude supports. Response uses 0.0–6.5 in 0.1 steps; exposure uses
midpoints 0.05–6.55. Identical PMFs therefore differ by +0.05 in mean/median point
actions and produce different Huber gradients. Baselines must not be pooled or
reused as a cross-grid ablation. Exposure runtime manifests/reports pin its
source/protocol hashes; the support is explicit there, not repeated as a numeric
array in each report.

Synthetic tests exercise exact alignment, forbidden-member decoding, response
mask/rate failure, full static reconstruction, epoch-window rejection and
complete v3 join membership. They use no real data.
