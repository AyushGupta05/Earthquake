# Detached resolution reproducibility audit

Date: 2026-10-09. Scope: read-only original AWS artifacts, local source inspection, and synthetic CPU checks. No GPU execution, dataset mutation, training launch, or existing-module edit was performed.

## Result

**The historical mismatch is real, but its specific cause is not yet established.** Common code, recorded configuration, row selection, teacher targets, optimizer groups, scheduler state, and final CPU/CUDA RNG state agree. The detached mathematical objective should give the same backbone derivative, and this was verified bitwise for the actual model and training functions on CPU, including batch size 512. Parent-scheduled crossed GPU probes now demonstrate present CUDA nonrepeatability under default settings, removed in the tested deterministic configurations (see addendum). This is a concrete plausible mechanism, not forensic proof of the unique historical root cause. Do not interpret the detached run's score difference as an auxiliary learning effect, and do not claim an exact negative control from this run.

Run directories under `/home/ec2-user/Earthquake/results/2026-10-09/phase2`:

- A: `resolution_cdf_distill_seed20261009_575b542bf64c_ea40c6efbc0a`
- B: `resolution_cdf_resolution_seed20261009_a9d09dd5d2c6_59488ca13f8b`

| Prefix | A final MAE | B final MAE | B − A |
|---|---:|---:|---:|
| 1 s | 0.3893834161 | 0.3906088080 | +0.0012253919 |
| 3 s | 0.3366781214 | 0.3381063905 | +0.0014282691 |
| 5 s | 0.3146085509 | 0.3163271875 | +0.0017186366 |

The backbone has diverged, not just the reporting code: 33 of 34 backbone state tensors differ at epoch 10. The largest parameter absolute difference is 0.2129566073 (`state_update.weight_ih`); that parameter's L2 difference is 4.2132201. Both final files are completed epoch 10. Backbone CE differs already in epoch 1 (A 2.9583054801, B 2.9584791135); teacher-distillation loss also differs (0.0475716313 vs 0.0475944095). Consequently, the cause precedes final validation and cannot be explained by reporting the added resolution loss alone.

## Provenance and configuration checks

All 19 source files common to the two archived manifests have exactly equal SHA-256 values. B additionally includes `future_growth.py`, `instrument_factor_ablation.py`, and `train_future_growth.py`, from the manifest's directory glob; the resolution runner does not import those modules. Key common hashes:

| File | SHA-256 |
|---|---|
| `train_resolution.py` | `ef83db6328a00c784f2fe9e3f2aa897f2f4aa43af35be36afd888fa41bb79db6` |
| `resolution_distillation.py` | `f9288212eddd6bb4d90ad4058b77f6f2c1a1accba8b3bf3a5a032776874c662d` |
| `sequential_models.py` | `17bf8529ffa00e51dc64885cf2bc09e6b83f8ad573040a2bd0f441fa2957ff44` |
| `train_sequential.py` | `0879691623eb11fe6850fac8ce0cf1eccf02fd03bc9ea1c5e2a364dea214ed19` |

Both use weighted Huber plus .075 CE, full 979,487 TRAIN rows, batch 512, seed 20261009, 10 fixed epochs, learning rate .0003, weight decay .0001, cosine minimum .00003, distillation weight 1, resolution weight 1, and unit envelope. Only intended control/head-detachment/head-description fields and measured runtime differ in `run.json`. Optimizer parameter groups and scheduler states in `latest.pth` are exactly equal. Wall times A 516.013 s, B 574.884 s; B performs extra head-loss computation, so this difference alone is not evidence of a changed environment.

Exact shared identities:

- TRAIN metadata `168b5d861804e9707f68125dc8bc9453c8e0a47a48ef4055a7920c6526f1535d`.
- VAL metadata `3e1b2781559fc1da8c1d1de03af3148f4399c556df84741ae1e38b32d476698f`.
- Ordered TRAIN row array `140cc844a19b7619a11580ca25e059a7c9800670768298956bf6cb6a86a5b653`.
- 3 s teacher checkpoint `4499557d002bc5e74a0d7843c1c666ff242ff57340495a93fd7c6d218891aadc`.
- 5 s teacher checkpoint `59591ae7b403acb30d71715bea33856ad9c6d1050ca44af7c1a3f592b7970bd0`.
- Complete ordered TRAIN 3 s teacher-CDF array `993abf077926d3545cd2cadb627c30bb0de5a1521d261ead92481b41efb06c5f`.
- Complete ordered TRAIN 5 s teacher-CDF array `0857a186cc5d4370f9d19a20769cf90678f40392cd81b95c66ef1320e1d05c14`.

The waveform cache `/data/Instance_windows_5s.hdf5` is 6,960,137,796 bytes, mtime 2026-09-03 18:43:30 UTC, predating both runs. Full waveform bytes were not hashed by the original runner or this bounded audit. Equal teacher CDF hashes strongly constrain input changes but do not logically prove every waveform byte was unchanged. Metadata content is independently hash-checked by the loader. Loader verifies cached magnitude/metadata alignment.

## RNG, graph, and optimizer reasoning

The model constructor is identical across controls; both construct the auxiliary Linear layer before zero-initializing it. `torch.manual_seed(seed)` runs after teacher inference and immediately before the student constructor. The backbone and auxiliary head contain **no dropout** or other intentional stochastic training operation. Per-epoch order is a CUDA `torch.randperm`; the runner does not archive per-epoch order hashes.

The epoch-10 checkpoint RNG states are bit-identical:

- CPU RNG SHA-256 `098a334ed5bd1787ef62646ba2b52880919cb0fb83c00c73a0ff8ef164b0f9e7`.
- One CUDA RNG SHA-256 `3e204c3e834955ddd634b4edb5c2869c0c4ed5869eaee6b1a9f78e49d587982d`.

This and the inspected call sequence provide strong evidence against changed random-number consumption. It does not substitute for archived order hashes or establish identical historical libraries/initialization numerics.

For unit-envelope detached B, the auxiliary loss is a function of `state.detach()` and a target `(teacher_cdf - current_cdf.detach())**2`. Therefore its derivative with respect to all backbone parameters is zero. `clip_student_gradients` clips backbone and auxiliary parameters independently, so head-gradient norm cannot shrink backbone gradients. AdamW states are per parameter; the common group settings do not couple the head gradient norm to backbone updates.

There is a real graph difference: `forecast_losses` still evaluates `0 * resolution_loss` in A, with the head input attached. B detaches this input and adds its nonzero head loss. A zero weight removes the mathematical derivative but retains graph nodes. This could affect kernel scheduling/accumulation; **it did not cause observable CPU drift in the checks below**, so it remains only a GPU-specific hypothesis, not a confirmed bug.

The runner sets `cudnn.benchmark=False` but not `torch.use_deterministic_algorithms(True)` or `cudnn.deterministic=True`. PyTorch 2.8 documents that disabling benchmarking chooses an algorithm consistently but does not require the algorithm itself to be deterministic; CUDA also has cuBLAS reproducibility settings. The same documentation states `manual_seed` seeds CPU and CUDA. [PyTorch 2.8 reproducibility](https://docs.pytorch.org/docs/2.8/notes/randomness.html). Floating-point operation order can change results because addition is not associative; deterministic execution does not promise equivalence between different mathematical implementations. [PyTorch 2.8 numerical accuracy](https://docs.pytorch.org/docs/2.8/notes/numerical_accuracy.html).

Historical manifests and discovered launch logs do not record GPU model, driver, Torch/cuDNN versions, TF32 settings, deterministic flags, or relevant environment variables. The current read-only CPU process reports Torch 2.8.0+cu128, CUDA build 12.8, cuDNN 91002, Python 3.9.25. The installed Torch version file predates the runs (2026-08-19), but current environment evidence is not a complete historical runtime record.

## Synthetic CPU checks actually executed

`work/resolution_cpu_diagnostic.py` imports the actual production model, loss, and clipping functions. It creates deterministic synthetic waveforms, magnitudes, and teacher CDFs with a separate CPU generator, supplies exactly the same minibatches to all variants, and compares logits, unclipped backbone gradients, and post-AdamW backbone parameters at every step:

1. A vs identical A repeat.
2. A vs distillation with detached features, isolating the zero-weight attached branch.
3. A vs detached trained resolution B.
4. Detached distillation vs B.
5. Detached distillation vs separate baseline backward followed by a detached head-only backward.

All five comparisons were **bitwise equal at every step** in both runs:

- 8 steps, batch 8, 24 synthetic records, 2 CPU threads: `work/resolution_cpu_diagnostic.json`.
- 2 steps, batch 512, 512 synthetic records, 2 CPU threads: `work/resolution_cpu_batch512.json`.

These test the implemented derivative/update isolation. They do not replicate real training amplitudes, full epoch order, CUDA kernels, or 19,140 optimization steps. No inference about the scale of 10-epoch CUDA drift follows from CPU equality alone.

## Small next diagnostic, prepared but not executed on GPU

Parent may schedule the same script on the original device when its queue is idle. It needs no dataset or training output directory. Start with 8 steps and batch 512, comparing A-repeat separately from A-vs-B:

```bash
.venv/bin/python resolution_cpu_diagnostic.py --repo /home/ec2-user/Earthquake --device cuda --batch-size 512 --records 512 --steps 8
CUBLAS_WORKSPACE_CONFIG=:4096:8 .venv/bin/python resolution_cpu_diagnostic.py --repo /home/ec2-user/Earthquake --device cuda --batch-size 512 --records 512 --steps 8 --deterministic
```

The filename describes the already-executed default; `--device cuda` is explicit and opt-in. Save stdout from each invocation and record device/runtime settings. The script reports the first forward/gradient/update difference per comparison.

- If A-vs-A drifts under default settings and becomes exact with deterministic settings, we have demonstrated nondeterministic execution in the diagnostic; locate the first differing operation before claiming the historical cause.
- If A-vs-A is exact but A-vs-B differs, inspect the first backward mismatch, the attached-zero-branch control, and the serial-backward control. This distinguishes a graph-dependent numerical effect from repeated-operation nondeterminism.
- If both are exact, repeat the first few actual TRAIN batches at matched initialization/order and log tensor hashes; this needs a separate scheduled read-only-data GPU probe, not a full rerun.
- Only after that should a deterministic full negative-control rerun be used to establish exact replay. Archive initial parameters, each epoch's order hash, data/target identities, hardware/software versions, and backend flags. Existing historical results should retain an explicit numerical-reproducibility limitation.

## Evidence files

- `work/resolution_checkpoint_audit.py`: read-only checkpoint inspection helper, executed through SSH with CUDA hidden.
- `work/resolution_checkpoint_audit.json`: complete retrieved manifests/configuration/history, RNG comparison, parameter differences, current environment.
- `work/resolution_cpu_diagnostic.py`: bounded synthetic diagnostic; no artifact/data mutation.
- `work/resolution_cpu_diagnostic.json`, `work/resolution_cpu_batch512.json`: CPU diagnostic results.

No repository changes or commits were made for this audit.

## Parent-scheduled CUDA follow-up (2026-10-09)

After this subagent completed its CPU-only audit, the parent scheduled four bounded GPU executions on the original worker after its active training queue. This subagent did not launch them. All four use the reviewed synthetic diagnostic, not real TRAIN data. The crossed conditions avoid confounding batch size or update count with the deterministic setting.

| CUDA setting | Batch / records / updates | Same-control-repeat final parameter max difference | All five pairs exact at every observed forward/gradient/update? |
|---|---:|---:|---|
| Default | 8 / 24 / 8 | 0.0002150386572 | No |
| Default | 512 / 512 / 2 | 0.0004402734339 | No |
| Deterministic + cuBLAS config | 8 / 24 / 8 | 0 | Yes |
| Deterministic + cuBLAS config | 512 / 512 / 2 | 0 | Yes |

The deterministic runs set `torch.use_deterministic_algorithms(True)` and `CUBLAS_WORKSPACE_CONFIG=:4096:8`. Default runs differ even between two identical distillation controls, so detachment/auxiliary-gradient leakage is not needed to produce the present discrepancy. In the deterministic probes the trained detached auxiliary, attached zero-weight branch, and serial-backward controls all match exactly, supporting gradient isolation for those tested computations.

This **demonstrates current numerical nonrepeatability** of the default CUDA path for this implementation, across both tested sizes. It does not identify the specific kernel, uniquely reconstruct the historical environment, or quantify 19,140-step real-data drift. Historical exact negative-control claims remain unsupported; next matched training runs should use deterministic settings and a fresh raw baseline with recorded initial/order hashes. No statistical learning gain can be attributed to a detached head.

Retrieved primary experiment files under `work/repo/results/2026-10-09/resolution_repro_probe/`:

- `cuda_default.json` SHA-256 `e1ee513911f05b5b2a1df7e3c2b93b536376337473080a36a8fc3361f6eb6df4`.
- `cuda_default_batch512.json` SHA-256 `df8a6ea8da2ed37cfe699386ef37d1b16f568b9fbfc46dd1a49f05a8d6c11dc0`.
- `cuda_deterministic_batch512.json` SHA-256 `7b7845993e8c1dc122e706f3ccd5bedf099c2d406ede2b1b0a5a6c73c81459cb`.
- `cuda_deterministic_batch8.json` SHA-256 `f0d06f259b2194fbbdd4dcdeff6415e6ed7e2e6ee01155137607352784a631d5`.
