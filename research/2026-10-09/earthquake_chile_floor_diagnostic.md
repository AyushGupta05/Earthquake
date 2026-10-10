# Chile likelihood-floor diagnostic — completed negative result

The full 25-pretraining/100-event-epoch baseline completed successfully and selected epoch 97 by TRAIN-calibration NLL. Its proposed likelihood-floor mechanism **fails the frozen incidence gate**: zero of the 20 MA≥5.5 fitting earthquakes jointly have attenuation below 0.1 and mean underestimation above 0.5 at two or more of 1/3/5 seconds. The Huber continuation is therefore not launched.

This tests the current selected checkpoint, not historical training causality. It does not show that the additive floor was harmless earlier, that proper Gaussian likelihood is universally worse, or that early magnitude error is irreducible. A normalized Huber density and the likelihood-floor attenuation identity are established prior art; no novelty or benchmark-superiority claim follows.

| Deadline | Minimum gradient-retention factor across 20 tail events | Median tail mean underestimation | Largest tail mean underestimation | Jointly suppressed/underestimated tail events |
|---:|---:|---:|---:|---:|
| 1 s | 0.963100 | 0.426975 | 3.980140 | 0 |
| 3 s | 0.999597 | −0.025123 | 1.318133 | 0 |
| 5 s | 0.999999 | −0.011144 | 0.095728 | 0 |

These are **TRAIN fitting diagnostics**, not validation errors. Negative underestimation means overprediction. A large one-second error can coexist with retained likelihood gradients because mixture components retain density at the true label; point error alone does not establish saturation.

The fixed diagnostic evaluated 1,371 distinct fitting events: all 20 tail events, up to 1,024 selected by event hash in each prespecified bulk stratum, with all available stations under the source cap. It made no optimizer steps, calibration/DEV/TEST forwards, or held-out metric selections. It finished in 199.73 seconds on the dedicated A10G under a 600-second outer timeout, 12 GiB task memory limit and verified automatic instance stop. All four output hashes and nine input pins verify. Independent parent replay agrees on Gaussian log-density, attenuation, native means, analytic proper/floored output gradients and the exact event gate; the largest analytic replay difference is below 3e−12. It did not independently rerun the model or every hypothetical Huber calculation.

The source passed 24 focused synthetic tests, clean Codex review and promoted-runtime testing. Completion guards were corrected to the actual baseline before completed diagnostic access. An initial STARTED-only attempt was canceled after finding missing deterministic settings; its directory and source are preserved. The final run matches baseline determinism and preserves TF32 defaults. These corrections do not change population, model, mathematical quantities or thresholds.

Completed baseline checkpoint/history and diagnostic outputs are preserved locally and on the worker’s durable EBS storage. The dedicated worker is verified stopped after its GPU became idle; its EBS storage is retained. Further research continues; no new head fit or speculative covariance run is earned by these results. Chile TEST waveforms remain unopened.

[Hash-bound replay receipt](phase2/chile_floor_diagnostic/real_v2/parent_replay.json) · [Source and execution handoff](phase2/chile_floor_diagnostic/handoff.json) · [Prior-art limits](earthquake_chile_density_claim_audit.md)
