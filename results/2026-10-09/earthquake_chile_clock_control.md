# Matched early-clock continuation

The comparison tests whether allocating training updates to 1, 3 and 5 seconds improves the deployment baseline. This is a known-method control: the port already contains a discrete cutoff sampler. The four-fit grid launched on the owned A10G at23:00:57 UTC on10October and completed normally. Independent replay verifies an **inconclusive** frozen gate; the full [results](earthquake_chile_clock_results.md) retain all tradeoffs and sparse tail cases.

Four serial fits use two seeds, with uniform-source and discrete-deadline arms. Every fit starts from the same selected epoch-97 checkpoint, retains the original TRAIN partition and uses six epochs, fresh Adam at 9e-6, the same five-Gaussian loss and paired augmentation streams. Final epoch six is fixed. All four fits must finish before calibration or DEV evaluation; TEST remains sealed.

The implementation passed code-only Codex autoreview. All 28 invented-data tests passed on AWS with no skips. Invented CUDA replay produced identical loss, model, optimizer and trace; changing the clock preserved the six paired non-clock streams. The first 16 frozen TRAIN events reproduced all five-Gaussian parameters exactly at every deadline, with zero optimizer steps and no calibration/DEV/TEST forwards. These establish runtime correctness, not model quality or TensorFlow parity.

DEV contains one MA≥5.5 event and no MA≥6 events. Tail errors are descriptive. The fixed bulk gate, proper scores and worst-error measures are all reported; neither a bulk pass nor this training allocation establishes novelty or published-benchmark superiority.

The caps are 9,000 seconds per fit, 36,000 seconds total fitting and 39,600 seconds for the grid. The active cgroup was verified with CPU quota 200%, memory 12 GiB, maximum runtime 39,840 seconds and 120-second stop grace. Its maximum runtime ends at 10:04:57 UTC, before the worker's verified STOP deadline of **10:50:21 UTC on 11 October (11:50 London)**. The correct persistent data source is bound read-only; the 16-vCPU account quota is fully occupied. No automatic extension is permitted.

[Frozen protocol](../../research/2026-10-09/phase2/chile_clock_control/protocol.json) · [Reviewed handoff](../../research/2026-10-09/phase2/chile_clock_control/handoff.json) · [Source clock audit](../../research/2026-10-09/phase2/chile_training_clock_audit/AUDIT.md)
