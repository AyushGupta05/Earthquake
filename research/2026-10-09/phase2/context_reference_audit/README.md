# Independent contextual-reference pilot audit

This CPU-only auditor reads completed artifacts, never fits a model, and never runs model inference. It requires all six prespecified arms and two seeds for one deadline, a final `COMPLETE.json`, every artifact-manifest byte count/hash, and the reviewed eleven-file source identities from commit `6c31e29a979a979594117633d13271e4a6eb8b62`. The real protocol is 197,676 sampled TRAIN recordings, 15 epochs, 5 event folds, and 13 M≥4 validation events. It does not open TEST.

It checks exact validation target/event/trace alignment, TRAIN/validation separation, teacher event exclusions, inverse-Bernoulli variance weights (epsilon .01, cap 25 before per-record mean-one normalization), the seeded within-fold donor bijection and weighted TRAIN-average vector. It reconstructs student and teacher initialization hashes and CPU shuffle sequences and checks each final checkpoint hash. CUDA is hidden before torch import; parameter initialization is on CPU only.

The archived float32 probability arrays are validated and normalized to unit mass for recomputed continuous-label CRPS and categorical NLL. NLL is for the original 66 discrete magnitude bins, not a continuous-density likelihood. Saved target probability zero is reported as infinite (JSON null with explicit status/count), never replaced with an arbitrary floor. Original float64 mean/median predictions are checked against explicit asymmetric IEEE float32 rounding intervals, ensemble convexity, and float64 CDF crossing-increment bounds and then used for point metrics so ambiguous rounded median ties cannot silently change reported decisions. CRPS is independently implemented by integrating squared CDF error and tested against the pairwise expectation identity, including off-grid/out-of-support labels.

## Provenance boundary

Raw 85-dimensional teacher input arrays were not archived. The auditor verifies saved per-fold normalizer values against reported hashes, exclusion row identities, source implementation, and preserved raw-input digest; it cannot independently recompute those values or reference forward probabilities. The source fits each teacher normalizer only on retained event-fold TRAIN rows. Upstream global count scaling remains target-free but was fitted using all TRAIN covariates. Teacher event cross-fitting does not make the student's existing all-TRAIN frozen CNN cross-fitted; the teacher excludes CNN logits/embeddings.

The optional strongest Huber comparison uses 979,487 TRAIN recordings rather than the pilot's 197,676. Its old runner has no COMPLETE/artifact manifest. These files are hashed and row-aligned only; comparison is descriptive, not causal evidence for a loss improvement. Reused exploratory validation, manual P picks, released preprocessing, 13 tail events, and lack of independent external validation remain scientific limits.

## Outputs and interpretation

A successful audit creates `audit.json` atomically after `metrics.csv`, `tail_events.csv`, and `report.md`. Metrics include both seeds and their ensemble, both mean and median decisions, MAE/MedAE/RMSE, recording- and event-macro tail errors, worst-5% CVaR, continuous CRPS, and discrete NLL. Individual tail-event deltas are included against every comparator. No best arm is selected and no weights or thresholds are tuned.

A context-specific hypothesis needs improvement over both within-fold shuffled and TRAIN-average weights, plus assessment against ordinary CRPS, ranked BCE, and properized AD. A win only over ordinary CRPS is insufficient evidence for context specificity. A method can trade average error for tail error; report both rather than proclaiming a win from one metric.

Example on the original authorized host, from `/home/ec2-user/Earthquake`:

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python tmp/context_reference_audit/audit.py --run /mnt/eew-research/runs/COMPLETED_RUN --validation-reference results/2026-10-09/validation_1s.npz --output tmp/context_reference_audit/audit_1s
```

Focused tests: `CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python -m unittest discover -s tmp/context_reference_audit -p test_audit.py -v`.

This directory contains research audit tooling and evidence only. No GPU launch, live training modification, or repository commit is part of its scope.

Raw mean/median identity is deliberately checked more strictly than the source loader’s allowed logit re-extraction drift. If it fails, this stronger empirical audit is inconclusive; that does not itself imply the training implementation is invalid. All three actual deadlines pass this stronger check.

Closeout: all 14 focused CPU tests pass (1.449 s); final isolated Codex autoreview clean (0.92). All three real `_final` audits pass 34 manifested files each. `verification.json` records code/report/review hashes. `conclusion.md` preserves the negative experimental result. The `review_clone` directory is disposable review scratch, not a deliverable or commit target.
