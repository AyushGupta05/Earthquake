# EEW distribution research — 9 October 2026

This directory records an exploratory audit and literature-informed experiments. Nothing here establishes deployment readiness or state-of-the-art performance. The existing validation set has already been used for model selection and many previous experiments; cross-fitting a new readout does not make it an untouched test.

## Current work

- `audit_and_export.py`: verify metadata event separation, magnitude support, cache lengths, complete target alignment, and sampled raw waveform identity; export full validation logits at exactly 1, 3, and 5 seconds.
- `literature_review.md`: source-backed research synthesis and proposed method.
- `experiment_results.md`: completed quantitative comparisons and conclusions.
- `distribution_experiment.py`: event-separated mean/probe/full-distribution readouts.
- `frozen_head_pilot.py`: bounded final-layer CE/CDF-score comparison.
- `experiment_log.md`: executed work, results, and failures.

The original notebooks use `instancepipelineprior`, whose cache is 300 samples. In particular, `investigateprior1s.ipynb` and `investigateentropy1sfixed.ipynb` import that loader. A checkpoint filename alone is not evidence of the evaluated observation duration. New exports use explicit caches and fail on a length mismatch.

The original CNN has **66** bins, centers 0.05 through 6.55. This differs from the informal 64-value description. The September PDF's correction uses M>=4 tail weighting, not M>=6. A distributional tree trained on observed labels may expose fewer classes than the CNN.

## Reproduction

From the repository root on the existing AWS host:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python research/2026-10-09/audit_and_export.py
.venv/bin/python research/2026-10-09/distribution_experiment.py --input results/2026-10-09/validation_1s.npz --output results/2026-10-09/readouts_1s
.venv/bin/python research/2026-10-09/distribution_experiment.py --input results/2026-10-09/validation_3s.npz --output results/2026-10-09/readouts_3s
.venv/bin/python research/2026-10-09/distribution_experiment.py --input results/2026-10-09/validation_5s.npz --output results/2026-10-09/readouts_5s
timeout 3600 .venv/bin/python research/2026-10-09/frozen_head_pilot.py
```

The dataset volume is mounted read-only at `/data`. Outputs belong in `results/2026-10-09`; waveform data, checkpoint files, and prediction arrays must not enter Git. Aggregate JSON/Markdown results are versioned. Existing source and trained checkpoints remain intact.

All runs above completed. The fresh duration-correct baseline overall/M>=4 MAEs are 0.414320/0.899153 (1s), 0.363262/0.751692 (3s), and 0.331355/0.651258 (5s). No tested correction met the joint tail/bulk objective. The original investigation notebooks are preserved; use the audited scripts for these comparisons.
