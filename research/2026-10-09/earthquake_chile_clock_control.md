# Matched early-clock continuation

The prospective comparison tests whether allocating training updates to 1, 3 and 5 seconds improves the deployment baseline. This is a known-method control: the port already contains a discrete cutoff sampler. No new fit has started.

Four serial fits use two seeds, with uniform-source and discrete-deadline arms. Every fit starts from the same selected epoch-97 checkpoint, retains the original TRAIN partition and uses six epochs, fresh Adam at 9e-6, the same five-Gaussian loss and paired augmentation streams. Final epoch six is fixed. All four fits must finish before calibration or DEV evaluation; TEST remains sealed.

The implementation passed code-only Codex autoreview. Local invented-data tests passed 27 of 28, with one explicit h5py skip. All 28 worker tests, invented CUDA equality and the frozen first-16 TRAIN replay remain prerequisites to fitting.

DEV contains one MA≥5.5 event and no MA≥6 events. Tail errors are descriptive. The fixed bulk gate, proper scores and worst-error measures are all reported; neither a bulk pass nor this training allocation establishes novelty or published-benchmark superiority.

The caps are 9,000 seconds per fit, 36,000 seconds total fitting, 39,600 seconds for the grid and a verified worker STOP within 43,200 seconds. No automatic extension is permitted.

[Frozen protocol](phase3/chile_clock_control/protocol.json) · [Reviewed handoff](phase3/chile_clock_control/handoff.json) · [Source clock audit](phase2/chile_training_clock_audit/AUDIT.md)
