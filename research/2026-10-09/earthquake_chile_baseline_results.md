# Completed Chile TEAM-style baseline

The deterministic baseline completed 25 station-pretraining and 100 event-training epochs and exited successfully. TRAIN-calibration proper NLL selected epoch 97; DEV was reported only after selection. The checkpoint and full histories are preserved on durable worker storage and locally. Chile TEST waveforms remain unopened. The dedicated worker is currently verified stopped.

| Network-first-P deadline | DEV mean-action MAE | DEV mean-action MedAE | DEV CVaR95 | DEV CRPS | Proper mixture NLL |
|---:|---:|---:|---:|---:|---:|
| 1 s | 0.161993 | 0.125877 | 0.597678 | 0.115985 | -0.182958 |
| 3 s | 0.105980 | 0.081409 | 0.409228 | 0.075693 | -0.596651 |
| 5 s | 0.083272 | 0.062825 | 0.332433 | 0.059957 | -0.816584 |

These are 9,614 event-level DEV errors under the port's controlled protocol, not a matched reproduction of a published table. MA is the supplied Chile amplitude magnitude; it is not interchangeable with Mw or INSTANCE ML. DEV has 48 MA≥4 events, six MA≥5, one MA≥5.5 and none MA≥6. The existing TRAIN-calibration subset has two MA≥5.5 events. Neither supplies adequate large-earthquake support for a foundational tail-performance claim. TEST metadata previously established 30 MA≥5.5 events, but those waveform predictions stay sealed while methods and final comparisons are chosen.

The current model uses a continuous five-Gaussian distribution, network-aligned multistation data and causal prefix masking/demeaning. It retains the author's additive density floor, magnitude smoothing/resampling and station-blinding laws. Documented departures include an internal TRAIN-calibration partition, per-event rather than per-batch cutoff draws and the corrected half-open prefix mean. TensorFlow numerical parity has not been established. Single-model versus ensemble and time-origin differences also prevent direct comparison with unrelated published errors.

The completed likelihood-floor diagnostic fails its frozen incidence gate; no Huber continuation is earned. A matched, fixed-budget source-clock versus 1/3/5-clock fine-tuning control is being prepared. Its purpose is to test optimization allocation with equal starting weights, paired random streams and fixed final checkpoints. It is a known-method control and cannot establish tail generalization from one DEV tail event.

[Preservation manifest](phase2/chile_completed_baseline_20261010/preservation_manifest.json) · [Completed floor diagnosis](earthquake_chile_floor_diagnostic.md) · [Source clock audit](phase2/chile_training_clock_audit/AUDIT.md)
